import json
import uuid
from typing import Optional

from app.database import db_session


def save_camera_path(scene_id: str, name: str, duration: float, fps: int,
                     camera_mode: str, interpolation: str, keyframes: list[dict],
                     path_id: str = None) -> dict:
    if path_id:
        # 更新已有
        with db_session() as conn:
            conn.execute(
                """UPDATE camera_paths
                   SET name=?, duration=?, fps=?, camera_mode=?, interpolation=?,
                       keyframes=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (name, duration, fps, camera_mode, interpolation, json.dumps(keyframes), path_id),
            )
    else:
        path_id = f"path_{uuid.uuid4().hex[:12]}"
        with db_session() as conn:
            conn.execute(
                """INSERT INTO camera_paths (id, scene_id, name, duration, fps, camera_mode, interpolation, keyframes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (path_id, scene_id, name, duration, fps, camera_mode, interpolation, json.dumps(keyframes)),
            )

    return {"id": path_id, "name": name, "scene_id": scene_id, "keyframes": keyframes}


def get_camera_path(path_id: str) -> Optional[dict]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM camera_paths WHERE id = ?", (path_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["keyframes"] = json.loads(d["keyframes"])
        return d


def list_camera_paths(scene_id: str = None) -> list[dict]:
    with db_session() as conn:
        if scene_id:
            rows = conn.execute(
                "SELECT * FROM camera_paths WHERE scene_id = ? ORDER BY updated_at DESC",
                (scene_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM camera_paths ORDER BY updated_at DESC").fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["keyframes"] = json.loads(d["keyframes"])
            results.append(d)
        return results


def delete_camera_path(path_id: str) -> bool:
    with db_session() as conn:
        cur = conn.execute("DELETE FROM camera_paths WHERE id = ?", (path_id,))
        return cur.rowcount > 0
