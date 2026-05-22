import json
import uuid
import os
from typing import Optional

from app.config import MODELS_DIR
from app.database import db_session
from app.meshy_client import MeshyClient
from app.blender_generator import generate_scene as blender_generate

meshy = MeshyClient()


def create_scene(prompt: str) -> dict:
    """提交 Text-to-3D 生成任务，返回 scene 记录"""
    scene_id = f"scene_{uuid.uuid4().hex[:12]}"

    try:
        task = meshy.create_preview_task(prompt=prompt)
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Meshy API 调用失败: {e}"}

    with db_session() as conn:
        conn.execute(
            "INSERT INTO scenes (id, user_prompt, meshy_task_id, status) VALUES (?, ?, ?, ?)",
            (scene_id, prompt, task["task_id"], "generating")
        )

    return {
        "id": scene_id,
        "prompt": prompt,
        "task_id": task["task_id"],
        "status": "generating",
    }


def check_and_update_scene(scene_id: str) -> dict:
    """检查 Meshy 任务状态，如果完成则下载 GLB"""
    with db_session() as conn:
        row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        if not row:
            return {"error": f"Scene {scene_id} 不存在"}

        if row["status"] not in ("generating", "pending"):
            return dict(row)

        task_id = row["meshy_task_id"]
        try:
            result = meshy.get_task_status(task_id)
        except Exception as e:
            return dict(row) | {"error": str(e)}

        if result["status"] == "completed":
            glb_url = result["model_urls"].get("glb")
            if glb_url:
                dest = MODELS_DIR / f"{scene_id}.glb"
                meshy.download_model(glb_url, str(dest))
                conn.execute(
                    "UPDATE scenes SET status='ready', model_path=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (str(dest), scene_id),
                )

            if result.get("thumbnail_url"):
                import httpx
                thumb_dest = MODELS_DIR / f"{scene_id}_thumb.png"
                try:
                    r = httpx.get(result["thumbnail_url"], timeout=30)
                    r.raise_for_status()
                    with open(thumb_dest, "wb") as f:
                        f.write(r.content)
                    conn.execute("UPDATE scenes SET thumbnail_path=? WHERE id=?", (str(thumb_dest), scene_id))
                except Exception:
                    pass

            return {
                "id": scene_id,
                "user_prompt": row["user_prompt"],
                "status": "ready",
                "model_url": f"/static/models/{scene_id}.glb",
            }

        elif result["status"] == "failed":
            err = result.get("error", "未知错误")
            conn.execute(
                "UPDATE scenes SET status='failed', error_message=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (err, scene_id),
            )
            return {"id": scene_id, "status": "failed", "error": err}

        # 仍在生成中
        return {
            "id": scene_id,
            "status": "generating",
            "progress": result.get("progress", 0),
            "preview_url": result.get("preview_url"),
        }


def get_scene(scene_id: str) -> Optional[dict]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("model_path") and os.path.exists(d["model_path"]):
            d["model_url"] = f"/static/models/{os.path.basename(d['model_path'])}"
        return d


def create_scene_with_blender(prompt: str) -> dict:
    """使用 Blender 本地生成 3D 场景 (无需 Meshy API)"""
    scene_id = f"scene_{uuid.uuid4().hex[:12]}"

    with db_session() as conn:
        conn.execute(
            "INSERT INTO scenes (id, user_prompt, status) VALUES (?, ?, ?)",
            (scene_id, prompt, "generating"),
        )

    result = blender_generate(prompt, scene_id=scene_id)

    if "error" in result:
        with db_session() as conn:
            conn.execute(
                "UPDATE scenes SET status='failed', error_message=? WHERE id=?",
                (result["error"], scene_id),
            )
        return {"id": scene_id, "status": "failed", "error": result["error"]}

    model_path = result["model_path"]
    with db_session() as conn:
        conn.execute(
            "UPDATE scenes SET status='ready', model_path=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (model_path, scene_id),
        )

    return {
        "id": scene_id,
        "prompt": prompt,
        "status": "ready",
        "model_url": result["model_url"],
        "template": result.get("template"),
    }


def list_scenes(status: str = None) -> list[dict]:
    with db_session() as conn:
        if status:
            rows = conn.execute("SELECT * FROM scenes WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM scenes ORDER BY created_at DESC").fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if d.get("model_path") and os.path.exists(d["model_path"]):
                d["model_url"] = f"/static/models/{os.path.basename(d['model_path'])}"
            results.append(d)
        return results
