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

