"""
Meshy API 封装 — Text-to-3D
文档: https://docs.meshy.ai/api-v2/text-to-3d
"""
import time
import httpx
from app.config import MESHY_API_KEY, MESHY_API_BASE


class MeshyClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {MESHY_API_KEY}",
            "Content-Type": "application/json",
        }

    def _check_key(self):
        if not MESHY_API_KEY:
            raise RuntimeError("MESHY_API_KEY 未设置，请在环境变量中配置")

    def create_preview_task(self, prompt: str, negative_prompt: str = "",
                            art_style: str = "realistic") -> dict:
        """
        创建 Text-to-3D preview 任务
        返回: {"task_id": "...", "status": "pending", "created_at": ...}
        """
        self._check_key()
        body = {
            "mode": "preview",
            "prompt": prompt,
            "negative_prompt": negative_prompt or "low quality, blurry, ugly, distorted",
            "art_style": art_style,
            "should_remesh": True,
        }
        r = httpx.post(
            f"{MESHY_API_BASE}/text-to-3d",
            json=body,
            headers=self.headers,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return {"task_id": data["result"], "status": "pending"}

    def get_task_status(self, task_id: str) -> dict:
        """
        查询任务状态
        返回: {"status": "pending|in_progress|completed|failed",
               "progress": 0-100,
               "model_urls": {"glb": "...", "fbx": "...", ...} | None,
               "error": ... | None}
        """
        self._check_key()
        r = httpx.get(
            f"{MESHY_API_BASE}/text-to-3d/{task_id}",
            headers=self.headers,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        result = {
            "status": data.get("status", "pending"),
            "progress": data.get("progress", 0),
            "preview_url": data.get("preview_url"),
            "thumbnail_url": data.get("thumbnail_url"),
        }
        if data.get("status") == "completed":
            result["model_urls"] = data.get("model_urls", {})
            result["thumbnail_url"] = data.get("thumbnail_url")
        if data.get("status") == "failed":
            result["error"] = data.get("error", {}).get("message", data.get("task_error", "Unknown error"))
        return result

    def download_model(self, url: str, dest_path: str) -> str:
        """下载 GLB 文件到本地"""
        r = httpx.get(url, timeout=120)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(r.content)
        return dest_path

    def poll_until_complete(self, task_id: str, timeout: int = 600, interval: int = 5) -> dict:
        """轮询直到任务完成或超时"""
        start = time.time()
        while time.time() - start < timeout:
            result = self.get_task_status(task_id)
            if result["status"] in ("completed", "failed"):
                return result
            time.sleep(interval)
        raise TimeoutError(f"任务 {task_id} 超时 ({timeout}s)")
