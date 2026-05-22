"""
AnchorVerse — Room Manager
WebSocket 事件路由 + Room 生命周期 + 位置同步 + 聊天中继
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


@dataclass
class PlacedObject:
    """用户放置的物件"""
    obj_id: str
    asset_key: str             # 物件类型: "cube_red", "chair_wood", etc.
    position: tuple
    rotation: tuple
    placed_by: str             # session_id


class Room:
    def __init__(self, room_id: str, scene_id: str, host_session: str):
        self.room_id = room_id
        self.scene_id = scene_id
        self.host_session = host_session
        self.users: dict[str, User] = {}
        self.objects: dict[str, PlacedObject] = {}   # 场景中的物件
        self.created_at = _now()
        self.last_broadcast = 0.0
        self._broadcast_task: Optional[asyncio.Task] = None

    @property
    def user_count(self) -> int:
        return len([u for u in self.users.values() if u.animation != "__disconnected"])

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
        }, exclude=session_id)

        # 如果房间空了，进入清理计时
        if not self.users:
            ROOMS.pop(self.room_id, None)

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
    active_count = sum(1 for u in room.users.values() if u.animation != "__disconnected")
    if active_count >= MAX_USERS_PER_ROOM:
        await websocket.send_json({"type": "error", "text": "房间已满"})
        await websocket.close()
        return

    session_id = _gen_id(12)
    display_name = join_msg.get("display_name", "Player")[:20]
    avatar_color = join_msg.get("avatar_color", "#6366f1")

    user = User(
        session_id=session_id,
        display_name=display_name,
        avatar_color=avatar_color,
        ws=websocket,
        joined_at=_now(),
    )
    room.users[session_id] = user

    # 发房间完整状态给新用户
    await websocket.send_json({
        "type": "room_state",
        "room_id": room.room_id,
        "scene_id": room.scene_id,
        "session_id": session_id,
        "users": [
            {
                "session_id": s,
                "display_name": u.display_name,
                "avatar_color": u.avatar_color,
                "p": list(u.position),
                "r": list(u.rotation),
                "a": u.animation,
            }
            for s, u in room.users.items()
            if u.animation != "__disconnected"
        ],
        "objects": [
            {
                "obj_id": o.obj_id,
                "asset_key": o.asset_key,
                "position": list(o.position),
                "rotation": list(o.rotation),
                "placed_by": "system" if o.placed_by == "__system" else o.placed_by[:12],
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

    # 启动位置广播（如果还没启动）
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
                obj_id = _gen_id(10)
                obj = PlacedObject(
                    obj_id=obj_id,
                    asset_key=data.get("asset_key", "cube_default"),
                    position=tuple(data.get("position", [0, 0, 0])),
                    rotation=tuple(data.get("rotation", [0, 0, 0, 1])),
                    placed_by=session_id,
                )
                room.objects[obj_id] = obj
                await room.broadcast({
                    "type": "object_placed",
                    "obj_id": obj_id,
                    "asset_key": obj.asset_key,
                    "position": list(obj.position),
                    "rotation": list(obj.rotation),
                    "placed_by": session_id[:12],
                })

            elif msg_type == "remove_object":
                target_id = data.get("obj_id", "")
                if target_id in room.objects:
                    del room.objects[target_id]
                    await room.broadcast({
                        "type": "object_removed",
                        "obj_id": target_id,
                        "removed_by": session_id[:12],
                    })

            elif msg_type == "move_object":
                target_id = data.get("obj_id", "")
                if target_id in room.objects:
                    room.objects[target_id].position = tuple(data.get("position", room.objects[target_id].position))
                    room.objects[target_id].rotation = tuple(data.get("rotation", room.objects[target_id].rotation))
                    await room.broadcast({
                        "type": "object_moved",
                        "obj_id": target_id,
                        "position": list(room.objects[target_id].position),
                        "rotation": list(room.objects[target_id].rotation),
                    }, exclude=session_id)

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

def create_room(scene_id: str) -> str:
    room_id = _gen_id(8)
    ROOMS[room_id] = Room(
        room_id=room_id,
        scene_id=scene_id,
        host_session="__pending",
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
        "users": [
            {"session_id": s[:8], "display_name": u.display_name}
            for s, u in room.users.items()
            if u.animation != "__disconnected"
        ],
    }


def list_active_rooms() -> list[dict]:
    return [
        {
            "room_id": r.room_id,
            "scene_id": r.scene_id,
            "user_count": r.user_count,
        }
        for r in ROOMS.values()
        if r.user_count > 0
    ]
