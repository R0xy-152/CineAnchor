import sqlite3
import os
from contextlib import contextmanager

from app.config import DATABASE_URL


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DATABASE_URL), exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY,
                user_prompt TEXT NOT NULL,
                meshy_task_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                model_format TEXT DEFAULT 'glb',
                model_path TEXT,
                thumbnail_path TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS camera_paths (
                id TEXT PRIMARY KEY,
                scene_id TEXT REFERENCES scenes(id) ON DELETE CASCADE,
                name TEXT NOT NULL DEFAULT 'Untitled',
                duration REAL NOT NULL DEFAULT 5.0,
                fps INTEGER NOT NULL DEFAULT 24,
                camera_mode TEXT NOT NULL DEFAULT 'orbit',
                interpolation TEXT NOT NULL DEFAULT 'catmull-rom',
                keyframes TEXT NOT NULL DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS room_objects (
                obj_id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                asset_key TEXT NOT NULL,
                position TEXT NOT NULL DEFAULT '[0,0,0]',
                rotation TEXT NOT NULL DEFAULT '[0,0,0,1]',
                placed_by TEXT NOT NULL DEFAULT '__system',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_room_objects_room
                ON room_objects(room_id);

            CREATE TABLE IF NOT EXISTS world_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'general',
                sky_color TEXT DEFAULT '#87ceeb',
                fog_color TEXT DEFAULT '#c8dce8',
                fog_near REAL DEFAULT 30,
                fog_far REAL DEFAULT 80,
                terrain_type TEXT DEFAULT 'floating_island',
                terrain_config TEXT DEFAULT '{}',
                ambient_light TEXT DEFAULT '#8899bb',
                ambient_intensity REAL DEFAULT 2.0,
                sun_color TEXT DEFAULT '#ffeedd',
                sun_intensity REAL DEFAULT 4.0,
                preview_url TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()


@contextmanager
def db_session():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Room Object 持久化 ──────────────────────────────────────

def persist_room_object(room_id: str, obj_id: str, asset_key: str,
                        position: list, rotation: list, placed_by: str):
    import json
    with db_session() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO room_objects (obj_id, room_id, asset_key, position, rotation, placed_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (obj_id, room_id, asset_key,
              json.dumps(position), json.dumps(rotation), placed_by))


def remove_room_object(obj_id: str):
    with db_session() as conn:
        conn.execute("DELETE FROM room_objects WHERE obj_id = ?", (obj_id,))


def load_room_objects(room_id: str):
    import json
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM room_objects WHERE room_id = ? ORDER BY created_at",
            (room_id,)
        ).fetchall()
    return [
        {
            "obj_id": r["obj_id"],
            "asset_key": r["asset_key"],
            "position": json.loads(r["position"]),
            "rotation": json.loads(r["rotation"]),
            "placed_by": r["placed_by"],
        }
        for r in rows
    ]


def save_room_objects_batch(room_id: str, objects: list):
    """批量保存房间物件（用于房间销毁时 dump）"""
    import json
    with db_session() as conn:
        conn.execute("DELETE FROM room_objects WHERE room_id = ?", (room_id,))
        for obj in objects:
            conn.execute("""
                INSERT INTO room_objects (obj_id, room_id, asset_key, position, rotation, placed_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (obj["obj_id"], room_id, obj["asset_key"],
                  json.dumps(obj["position"]), json.dumps(obj["rotation"]),
                  obj.get("placed_by", "__system")))


# ── World Templates ─────────────────────────────────────────

def seed_world_templates():
    """插入默认世界模板（幂等：已存在则跳过）"""
    templates = [
        ("floating_island", "浮空岛", "漂浮在云海中的神秘岛屿，绿草如茵",
         "fantasy", "#87ceeb", "#c8dce8", 30, 80,
         "floating_island", '{"island_height":10,"island_radius":4.5,"grass_color":"#4a7c3f"}',
         "#8899bb", 2.0, "#ffeedd", 4.0),
        ("castle_hall", "城堡大厅", "哥特式石柱大厅，烛光摇曳",
         "fantasy", "#1a1a2e", "#0a0a14", 20, 60,
         "castle_hall", '{"floor_size":12,"pillar_count":8,"wall_color":"#4a4a5a"}',
         "#332244", 1.5, "#ffcc88", 2.5),
        ("space_station", "太空站", "环绕地球轨道，星空无垠",
         "sci-fi", "#000011", "#000022", 50, 200,
         "space_station", '{"platform_radius":6,"ring_segments":4}',
         "#334466", 1.5, "#ffffff", 5.0),
        ("forest_clearing", "森林空地", "巨树环绕的林间空地，阳光透过叶隙",
         "nature", "#88ccaa", "#aaccee", 25, 70,
         "forest_clearing", '{"clearing_radius":5,"tree_count":20,"tree_height_range":[3,8]}',
         "#aacc88", 2.5, "#ffeedd", 3.0),
        ("desert_oasis", "沙漠绿洲", "金色沙丘中的一汪清泉，棕榈成荫",
         "nature", "#eeddbb", "#ddccaa", 40, 120,
         "desert_oasis", '{"oasis_radius":4,"dune_count":6,"palm_count":5}',
         "#ffddaa", 3.0, "#ffffff", 5.0),
        ("void_platform", "虚空平台", "极简黑色平台悬浮于霓虹虚空",
         "abstract", "#000000", "#111122", 10, 30,
         "void_platform", '{"platform_size":8,"grid_lines":true,"neon_color":"#7c3aed"}',
         "#222244", 1.0, "#ffffff", 3.0),
    ]
    with db_session() as conn:
        for t in templates:
            conn.execute("""
                INSERT OR IGNORE INTO world_templates
                (id, name, description, category, sky_color, fog_color, fog_near, fog_far,
                 terrain_type, terrain_config, ambient_light, ambient_intensity,
                 sun_color, sun_intensity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, t)


def list_world_templates(category: str = None):
    with get_conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM world_templates WHERE category = ? ORDER BY name", (category,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM world_templates ORDER BY category, name"
            ).fetchall()
    return [dict(r) for r in rows]


def get_world_template(template_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM world_templates WHERE id = ?", (template_id,)
        ).fetchone()
    return dict(row) if row else None
