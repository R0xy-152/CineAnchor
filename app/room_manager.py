"""
AnchorVerse — Room Manager
WebSocket 事件路由 + Room 生命周期 + 位置同步 + 聊天中继
+ 物件持久化 + 权限系统
"""
import json
import time
import uuid
import asyncio
import random
import string
from dataclasses import dataclass, field
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from app.database import (
    persist_room_object, remove_room_object, load_room_objects,
    save_room_objects_batch, get_world_template,
)

# ── 全局状态 ──────────────────────────────────────────────
ROOMS: dict[str, "Room"] = {}
POSE_BROADCAST_MS = 0.1      # 100ms = 10 Hz 批量广播
POSE_RATE_LIMIT_MS = 0.05    # 50ms = 20 Hz 单用户上报上限
MAX_USERS_PER_ROOM = 32
ROOM_GRACE_SECONDS = 30      # 最后一人离开后保留房间 30 秒

# ── 工具函数 ──────────────────────────────────────────────

def _now() -> float:
    return time.time()


def _gen_id(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


# ── 数据模型 ──────────────────────────────────────────────

@dataclass
class User:
    session_id: str
    display_name: str
    avatar_color: str
    ws: WebSocket
    position: tuple = (0, 1.6, 0)
    rotation: tuple = (0, 0, 0, 1)
    animation: str = "idle"
    last_pose_time: float = 0
    joined_at: float = 0
    is_host: bool = False


@dataclass
class PlacedObject:
    """用户放置的物件"""
    obj_id: str
    asset_key: str             # 物件类型: "cube_red", "chair_wood", etc.
    position: tuple
    rotation: tuple
    placed_by: str             # session_id


# ── 卡牌游戏引擎 (服务端) ────────────────────────────────

SUITS = ['spades', 'hearts', 'diamonds', 'clubs']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']


class ServerCardGame:
    """服务端卡牌游戏状态管理"""

    def __init__(self):
        self.deck: list[dict] = []
        self.hands: dict[str, list[dict]] = {}   # session_id -> [card]
        self.table: list[dict] = []
        self.discard: list[dict] = []
        self.players: list[str] = []             # session_id 按座位顺序
        self.turn_index: int = 0
        self.phase: str = 'setup'                # setup | playing | finished
        self._reset_deck()

    def _reset_deck(self):
        self.deck = [
            {"suit": s, "rank": r} for s in SUITS for r in RANKS
        ]

    def shuffle(self):
        random.shuffle(self.deck)

    def deal(self, cards_per: int = 2, table_count: int = 0):
        self.shuffle()
        self.hands = {}
        self.table = []
        self.discard = []
        for pid in self.players:
            self.hands[pid] = []
            for _ in range(cards_per):
                if self.deck:
                    self.hands[pid].append(self.deck.pop())
        for _ in range(table_count):
            if self.deck:
                self.table.append(self.deck.pop())
        self.phase = 'playing'
        self.turn_index = 0

    def play_card(self, player_id: str, card_id: str):
        """玩家出牌，返回打出的牌"""
        hand = self.hands.get(player_id, [])
        for i, c in enumerate(hand):
            cid = f"{c['rank']}_of_{c['suit']}"
            if cid == card_id:
                card = hand.pop(i)
                self.discard.append(card)
                return card
        return None

    def draw_card(self, player_id: str):
        """玩家抽牌"""
        if not self.deck:
            return None
        hand = self.hands.get(player_id)
        if hand is None:
            return None
        card = self.deck.pop()
        hand.append(card)
        return {"id": f"{card['rank']}_of_{card['suit']}", **card}

    def next_turn(self):
        self.turn_index = (self.turn_index + 1) % len(self.players)

    @property
    def current_player(self):
        if not self.players:
            return None
        return self.players[self.turn_index]

    def to_state(self, for_player: str = None):
        """返回游戏状态。for_player 指定时返回该玩家的完整手牌，其他玩家仅返回数量。"""
        hands_view = {}
        for pid, cards in self.hands.items():
            if pid == for_player:
                hands_view[pid] = [
                    {"id": f"{c['rank']}_of_{c['suit']}", **c} for c in cards
                ]
            else:
                hands_view[pid] = len(cards)  # 仅数量
        return {
            "phase": self.phase,
            "turn_index": self.turn_index,
            "current_player": self.current_player,
            "deck_remaining": len(self.deck),
            "table": self.table,
            "discard_size": len(self.discard),
            "discard_top": self.discard[-1] if self.discard else None,
            "hands": hands_view,
            "players": self.players,
        }

    def get_hand_for_player(self, player_id: str):
        return [
            {"id": f"{c['rank']}_of_{c['suit']}", **c}
            for c in self.hands.get(player_id, [])
        ]


class Room:
    def __init__(self, room_id: str, scene_id: str, host_session: str,
                 world_template: str = "floating_island"):
        self.room_id = room_id
        self.scene_id = scene_id
        self.host_session = host_session
        self.world_template = world_template
        self.users: dict[str, User] = {}
        self.objects: dict[str, PlacedObject] = {}
        self.created_at = _now()
        self.last_broadcast = 0.0
        self._broadcast_task: Optional[asyncio.Task] = None
        self.card_game: Optional[ServerCardGame] = None

        # 从 DB 恢复物件
        try:
            saved = load_room_objects(room_id)
            for obj_data in saved:
                self.objects[obj_data["obj_id"]] = PlacedObject(
                    obj_id=obj_data["obj_id"],
                    asset_key=obj_data["asset_key"],
                    position=tuple(obj_data["position"]),
                    rotation=tuple(obj_data["rotation"]),
                    placed_by=obj_data.get("placed_by", "__system"),
                )
            if saved:
                print(f"[Room {room_id}] 恢复 {len(saved)} 个物件")
        except Exception as e:
            print(f"[Room {room_id}] 物件恢复失败: {e}")

    @property
    def user_count(self) -> int:
        return len(self.users)

    @property
    def world_config(self) -> dict:
        """返回世界模板配置"""
        tpl = get_world_template(self.world_template)
        if tpl:
            return {
                "template_id": tpl["id"],
                "name": tpl["name"],
                "sky_color": tpl["sky_color"],
                "fog_color": tpl["fog_color"],
                "fog_near": tpl["fog_near"],
                "fog_far": tpl["fog_far"],
                "terrain_type": tpl["terrain_type"],
                "terrain_config": json.loads(tpl["terrain_config"]),
                "ambient_light": tpl["ambient_light"],
                "ambient_intensity": tpl["ambient_intensity"],
                "sun_color": tpl["sun_color"],
                "sun_intensity": tpl["sun_intensity"],
            }
        return {}

    async def broadcast(self, message: dict, exclude: str = None):
        """向房间所有用户发送消息"""
        dead = []
        for sid, user in self.users.items():
            if sid == exclude:
                continue
            try:
                await user.ws.send_json(message)
            except Exception:
                dead.append(sid)
        for sid in dead:
            await self.remove_user(sid, reason="connection_lost")

    async def remove_user(self, session_id: str, reason: str = "left"):
        user = self.users.pop(session_id, None)
        if user is None:
            return
        await self.broadcast({
            "type": "user_left",
            "session_id": session_id,
            "display_name": user.display_name,
            "reason": reason,
        }, exclude=session_id)

        # 如果房主离开，转移给下一个用户
        if user.is_host and self.users:
            new_host = next(iter(self.users.values()))
            new_host.is_host = True
            self.host_session = new_host.session_id
            await self.broadcast({
                "type": "host_changed",
                "new_host_session": new_host.session_id,
                "new_host_name": new_host.display_name,
            })

        # 如果房间空了，dump 物件到 DB 后清理
        if not self.users:
            self._dump_objects()
            ROOMS.pop(self.room_id, None)

    def _dump_objects(self):
        """房间销毁前将所有物件写入 DB"""
        if not self.objects:
            return
        try:
            obj_list = [
                {
                    "obj_id": o.obj_id,
                    "asset_key": o.asset_key,
                    "position": list(o.position),
                    "rotation": list(o.rotation),
                    "placed_by": o.placed_by,
                }
                for o in self.objects.values()
            ]
            save_room_objects_batch(self.room_id, obj_list)
            print(f"[Room {self.room_id}] 持久化 {len(obj_list)} 个物件")
        except Exception as e:
            print(f"[Room {self.room_id}] 物件持久化失败: {e}")

    async def pose_broadcaster(self):
        """后台协程：每 100ms 批量广播所有用户位置"""
        while self.room_id in ROOMS and self.users:
            now = _now()
            if now - self.last_broadcast >= POSE_BROADCAST_MS:
                self.last_broadcast = now
                pose_data = []
                for sid, user in self.users.items():
                    pose_data.append({
                        "session_id": sid,
                        "p": list(user.position),
                        "r": list(user.rotation),
                        "a": user.animation,
                    })
                if pose_data:
                    await self.broadcast({"type": "pose_broadcast", "users": pose_data})
            await asyncio.sleep(0.05)


# ── WebSocket 处理器 ──────────────────────────────────────

async def handle_room_ws(websocket: WebSocket, room_id: str):
    await websocket.accept()

    room = ROOMS.get(room_id)
    if not room:
        # 尝试从 DB 恢复房间（物件持久化）
        saved = load_room_objects(room_id)
        if saved:
            room = Room(room_id=room_id, scene_id='default', host_session='__restored')
            ROOMS[room_id] = room
            print(f"[Room {room_id}] 从 DB 恢复 ({len(saved)} 物件)")
            # 注意: Room.__init__ 已经调用了 load_room_objects，
            # 但 create_room 生成的随机 ID 不会匹配，只有这里显式传入时才会恢复。
            # 此处 saved 已加载，Room 构造时会再加载一次但那是正确的（新 room 无对象）。
        else:
            await websocket.send_json({"type": "error", "text": "房间不存在"})
            await websocket.close()
            return

    # 等待 join 消息（5 秒超时）
    try:
        join_msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
    except asyncio.TimeoutError:
        await websocket.close()
        return

    if join_msg.get("type") != "join_room":
        await websocket.close()
        return

    # 检查人数上限
    if len(room.users) >= MAX_USERS_PER_ROOM:
        await websocket.send_json({"type": "error", "text": "房间已满"})
        await websocket.close()
        return

    session_id = _gen_id(12)
    display_name = join_msg.get("display_name", "Player")[:20]
    avatar_color = join_msg.get("avatar_color", "#6366f1")

    # 第一个加入的就是房主
    is_host = (len(room.users) == 0)
    if is_host:
        room.host_session = session_id

    user = User(
        session_id=session_id,
        display_name=display_name,
        avatar_color=avatar_color,
        ws=websocket,
        joined_at=_now(),
        is_host=is_host,
    )
    room.users[session_id] = user

    # 发房间完整状态给新用户
    await websocket.send_json({
        "type": "room_state",
        "room_id": room.room_id,
        "scene_id": room.scene_id,
        "session_id": session_id,
        "is_host": is_host,
        "host_session": room.host_session,
        "world_template": room.world_template,
        "world_config": room.world_config,
        "users": [
            {
                "session_id": s,
                "display_name": u.display_name,
                "avatar_color": u.avatar_color,
                "p": list(u.position),
                "r": list(u.rotation),
                "a": u.animation,
                "is_host": u.is_host,
            }
            for s, u in room.users.items()
        ],
        "objects": [
            {
                "obj_id": o.obj_id,
                "asset_key": o.asset_key,
                "position": list(o.position),
                "rotation": list(o.rotation),
                "placed_by": o.placed_by,
            }
            for o in room.objects.values()
        ],
    })

    # 通知其他人
    await room.broadcast({
        "type": "user_joined",
        "session_id": session_id,
        "display_name": user.display_name,
        "avatar_color": user.avatar_color,
    }, exclude=session_id)

    # 启动位置广播
    if room._broadcast_task is None or room._broadcast_task.done():
        room._broadcast_task = asyncio.create_task(room.pose_broadcaster())

    # ── 消息循环 ──────────────────────────────────────────
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "pose_update":
                now = _now()
                if now - user.last_pose_time < POSE_RATE_LIMIT_MS:
                    continue
                user.last_pose_time = now
                user.position = tuple(data.get("p", user.position))
                user.rotation = tuple(data.get("r", user.rotation))
                user.animation = data.get("a", "idle")

            elif msg_type == "chat_message":
                text = (data.get("text", "") or "").strip()[:500]
                if text:
                    await room.broadcast({
                        "type": "chat_broadcast",
                        "session_id": session_id,
                        "display_name": user.display_name,
                        "text": text,
                        "timestamp": _now(),
                    })

            elif msg_type == "place_object":
                # 使用客户端提供的 obj_id，或生成新 ID
                obj_id = data.get("obj_id") or _gen_id(10)
                asset_key = data.get("asset_key", "cube_default")
                position = tuple(data.get("position", [0, 0, 0]))
                rotation = tuple(data.get("rotation", [0, 0, 0, 1]))

                obj = PlacedObject(
                    obj_id=obj_id,
                    asset_key=asset_key,
                    position=position,
                    rotation=rotation,
                    placed_by=session_id,
                )
                room.objects[obj_id] = obj

                # 持久化到 DB
                try:
                    persist_room_object(
                        room.room_id, obj_id, asset_key,
                        list(position), list(rotation), session_id,
                    )
                except Exception as e:
                    print(f"[Room {room.room_id}] 物件持久化失败: {e}")

                # 向所有人广播（包括发送者，用于确认 obj_id）
                await room.broadcast({
                    "type": "object_placed",
                    "obj_id": obj_id,
                    "asset_key": asset_key,
                    "position": list(position),
                    "rotation": list(rotation),
                    "placed_by": session_id,
                })

            elif msg_type == "remove_object":
                target_id = data.get("obj_id", "")
                obj = room.objects.get(target_id)

                if obj is None:
                    await websocket.send_json({
                        "type": "error", "text": "物件不存在",
                    })
                    continue

                # 权限检查：只有物主或房主可以删除
                if obj.placed_by != session_id and session_id != room.host_session:
                    await websocket.send_json({
                        "type": "error", "text": "你无权删除此物件",
                    })
                    continue

                del room.objects[target_id]
                try:
                    remove_room_object(target_id)
                except Exception as e:
                    print(f"[Room {room.room_id}] 删除物件失败: {e}")

                await room.broadcast({
                    "type": "object_removed",
                    "obj_id": target_id,
                    "removed_by": session_id,
                })

            elif msg_type == "move_object":
                target_id = data.get("obj_id", "")
                obj = room.objects.get(target_id)

                if obj is None:
                    continue

                new_pos = tuple(data.get("position", obj.position))
                new_rot = tuple(data.get("rotation", obj.rotation))
                obj.position = new_pos
                obj.rotation = new_rot

                # 更新 DB
                try:
                    persist_room_object(
                        room.room_id, target_id, obj.asset_key,
                        list(new_pos), list(new_rot), obj.placed_by,
                    )
                except Exception:
                    pass

                await room.broadcast({
                    "type": "object_moved",
                    "obj_id": target_id,
                    "position": list(new_pos),
                    "rotation": list(new_rot),
                }, exclude=session_id)

            elif msg_type == "kick_user":
                target_sid = data.get("target_session", "")
                # 只有房主可以踢人
                if session_id != room.host_session:
                    await websocket.send_json({
                        "type": "error", "text": "只有房主可以踢人",
                    })
                    continue
                if target_sid == session_id:
                    continue
                target_user = room.users.get(target_sid)
                if target_user is None:
                    continue
                try:
                    await target_user.ws.send_json({
                        "type": "kicked",
                        "text": "你被房主移出了房间",
                    })
                except Exception:
                    pass
                await room.remove_user(target_sid, reason="kicked")

            elif msg_type == "host_transfer":
                target_sid = data.get("target_session", "")
                if session_id != room.host_session:
                    await websocket.send_json({
                        "type": "error", "text": "只有房主可以转让",
                    })
                    continue
                target_user = room.users.get(target_sid)
                if target_user is None:
                    continue
                user.is_host = False
                target_user.is_host = True
                room.host_session = target_sid
                await room.broadcast({
                    "type": "host_changed",
                    "new_host_session": target_sid,
                    "new_host_name": target_user.display_name,
                })

            elif msg_type == "chess_move":
                await room.broadcast({
                    "type": "chess_move_broadcast",
                    "session_id": session_id,
                    "from": data.get("from"),
                    "to": data.get("to"),
                    "promotion": data.get("promotion", "Q"),
                }, exclude=session_id)

            # ── 卡牌游戏消息 ──────────────────────────────────

            elif msg_type == "card_init":
                # 初始化卡牌游戏（任何玩家都可以发起）
                if room.card_game is None:
                    cg = ServerCardGame()
                    cg.players = [s for s in room.users.keys()]
                    room.card_game = cg
                await room.broadcast({
                    "type": "card_game_state",
                    "state": room.card_game.to_state(),
                    "players": [
                        {
                            "session_id": s,
                            "display_name": u.display_name,
                            "avatar_color": u.avatar_color,
                        }
                        for s, u in room.users.items()
                    ],
                })

            elif msg_type == "card_deal":
                cg = room.card_game
                if cg is None:
                    cg = ServerCardGame()
                    cg.players = [s for s in room.users.keys()]
                    room.card_game = cg
                cards_per = data.get("cards_per", 2)
                table_count = data.get("table_count", 0)
                cg.deal(cards_per, table_count)

                # 给每位玩家单独发手牌
                for pid in cg.players:
                    if pid in room.users:
                        hand = cg.get_hand_for_player(pid)
                        await room.users[pid].ws.send_json({
                            "type": "card_dealt",
                            "hand": hand,
                            "table": cg.table,
                        })
                # 广播游戏状态（不含其他玩家手牌详情）
                await room.broadcast({
                    "type": "card_game_state",
                    "state": cg.to_state(),
                })

            elif msg_type == "card_play":
                cg = room.card_game
                if cg is None:
                    continue
                if session_id != cg.current_player:
                    await websocket.send_json({
                        "type": "error", "text": "不是你的回合",
                    })
                    continue
                card_id = data.get("card_id", "")
                card = cg.play_card(session_id, card_id)
                if card:
                    cg.next_turn()
                    await room.broadcast({
                        "type": "card_played",
                        "player_id": session_id,
                        "card_id": card_id,
                        "card": card,
                        "current_player": cg.current_player,
                        "turn_index": cg.turn_index,
                    })

            elif msg_type == "card_draw":
                cg = room.card_game
                if cg is None:
                    continue
                card = cg.draw_card(session_id)
                if card:
                    await room.broadcast({
                        "type": "card_drawn",
                        "player_id": session_id,
                        "card": card,
                    })

            elif msg_type == "card_shuffle":
                cg = room.card_game
                if cg is None:
                    continue
                cg.shuffle()
                await room.broadcast({
                    "type": "card_game_state",
                    "state": cg.to_state(),
                })

            elif msg_type == "card_reset":
                room.card_game = None
                await room.broadcast({
                    "type": "card_game_state",
                    "state": {"phase": "setup", "turn_index": 0,
                              "current_player": None, "deck_remaining": 52,
                              "table": [], "discard_size": 0,
                              "discard_top": None, "hands": {}, "players": []},
                    "players": [
                        {"session_id": s, "display_name": u.display_name,
                         "avatar_color": u.avatar_color}
                        for s, u in room.users.items()
                    ],
                })

            elif msg_type in ("voice_offer", "voice_answer", "voice_ice"):
                # WebRTC 信令中继：转发给目标用户
                target = data.get("target")
                if target and target in room.users:
                    try:
                        await room.users[target].ws.send_json({
                            "type": msg_type,
                            "from_session": session_id,
                            "data": data.get("data"),
                        })
                    except Exception:
                        pass

            elif msg_type == "emote":
                await room.broadcast({
                    "type": "emote_broadcast",
                    "session_id": session_id,
                    "emote": data.get("emote", "wave"),
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await room.remove_user(session_id)
        if room._broadcast_task and not room.users:
            room._broadcast_task.cancel()


# ── Room REST 辅助函数 ────────────────────────────────────

def create_room(scene_id: str, world_template: str = "floating_island") -> str:
    room_id = _gen_id(8)
    ROOMS[room_id] = Room(
        room_id=room_id,
        scene_id=scene_id,
        host_session="__pending",
        world_template=world_template,
    )
    return room_id


def get_room_info(room_id: str) -> Optional[dict]:
    room = ROOMS.get(room_id)
    if not room:
        return None
    return {
        "room_id": room.room_id,
        "scene_id": room.scene_id,
        "user_count": room.user_count,
        "object_count": len(room.objects),
        "host_session": room.host_session[:12],
        "world_template": room.world_template,
        "users": [
            {
                "session_id": s[:12],
                "display_name": u.display_name,
                "is_host": u.is_host,
            }
            for s, u in room.users.items()
        ],
    }


def list_active_rooms() -> list[dict]:
    return [
        {
            "room_id": r.room_id,
            "scene_id": r.scene_id,
            "user_count": r.user_count,
            "world_template": r.world_template,
        }
        for r in ROOMS.values()
        if r.user_count > 0
    ]
