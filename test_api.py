"""
CineAnchor API 自动化测试脚本
=============================
测试所有 API 端点：健康检查 → 场景管理 → 相机录制 → 视频渲染 → 数据清理
用法: python test_api.py [--base-url http://localhost:8000]
"""

import sys
import json
import time
import argparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.passed = 0
        self.failed = 0

    def _request(self, method: str, path: str, body: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")

        try:
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except HTTPError as e:
            body = e.read().decode()
            try:
                return json.loads(body)
            except Exception:
                return {"error": body, "status": e.code}
        except URLError as e:
            return {"error": str(e.reason)}

    def _test(self, name: str) -> None:
        print(f"\n{'='*50}")
        print(f"  {name}")
        print(f"{'='*50}")

    def _check(self, condition: bool, msg: str) -> None:
        if condition:
            self.passed += 1
            print(f"  ✅ {msg}")
        else:
            self.failed += 1
            print(f"  ❌ {msg}")

    def test_health(self):
        self._test("GET /health — 健康检查")
        resp = self._request("GET", "/health")
        self._check(resp.get("status") == "ok",
                    f"status=ok, render_mode={resp.get('render_mode')}, platform={resp.get('platform')}")
        return resp.get("render_mode")

    def test_root(self):
        self._test("GET / — 根路径")
        resp = self._request("GET", "/")
        self._check("message" in resp, f"message={resp.get('message')}")

    def test_list_scenes(self):
        self._test("GET /scenes — 列出场景")
        resp = self._request("GET", "/scenes")
        scenes = resp.get("scenes", {})
        self._check(len(scenes) > 0, f"Found {len(scenes)} scene(s): {list(scenes.keys())}")
        return list(scenes.keys())

    def test_create_scene(self, scene_id: str):
        self._test(f"POST /scene/create?scene_id={scene_id}")
        resp = self._request("POST", f"/scene/create?scene_id={scene_id}")
        self._check(resp.get("scene_id") == scene_id,
                    f"Created scene '{resp.get('scene_id')}', render_mode={resp.get('render_mode')}")

    def test_create_scene_invalid(self):
        self._test("POST /scene/create?scene_id=__nonexistent__ — 应返回 404")
        resp = self._request("POST", "/scene/create?scene_id=__nonexistent__")
        self._check("detail" in resp, f"Got expected error: {resp.get('detail', resp.get('error'))}")

    def test_record_frame(self, scene_id: str, frame_id: int, pose: dict):
        self._test(f"POST /camera/record_frame — frame {frame_id}")
        body = {
            "scene_id": scene_id,
            "frame_id": frame_id,
            "camera_pose": pose,
        }
        resp = self._request("POST", "/camera/record_frame", body)
        self._check(resp.get("depth_map_path") is not None,
                    f"Depth map: {resp.get('depth_map_path', resp.get('error'))}")
        return resp.get("depth_map_path")

    def test_record_frame_missing_scene(self):
        self._test("POST /camera/record_frame — 未初始化的场景应返回 400")
        body = {
            "scene_id": "never_created",
            "frame_id": 99,
            "camera_pose": {"position": {"x": 0, "y": 0, "z": 0}, "rotation": {"x": 0, "y": 0, "z": 0, "w": 1}},
        }
        resp = self._request("POST", "/camera/record_frame", body)
        self._check("detail" in resp, f"Got expected error: {resp.get('detail', resp.get('error'))}")

    def test_render_video(self, scene_id: str, prompt: str, fps: int = 24):
        self._test(f"POST /render/video — '{prompt[:40]}...' @ {fps}fps")
        body = {"scene_id": scene_id, "prompt": prompt, "fps": fps}
        resp = self._request("POST", "/render/video", body)
        self._check(resp.get("video_url") is not None,
                    f"Video: {resp.get('video_url', resp.get('error'))}")

    def test_render_video_no_depth_maps(self):
        self._test("POST /render/video — 无深度图应返回 400")
        body = {"scene_id": "no_depth_maps_scene", "prompt": "test"}
        resp = self._request("POST", "/render/video", body)
        self._check("detail" in resp, f"Got expected error: {resp.get('detail', resp.get('error'))}")

    def test_clear_data(self, scene_id: str):
        self._test(f"DELETE /clear_data/{scene_id} — 清理数据")
        resp = self._request("DELETE", f"/clear_data/{scene_id}")
        self._check(resp.get("message") is not None, f"Cleared: {resp.get('message')}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"  Results: {self.passed}/{total} passed, {self.failed} failed")
        print(f"{'='*50}")
        return self.failed == 0


# ---- 预设相机轨迹 ----
def make_pose(x, y, z, rx=0.0, ry=0.0, rz=0.0, rw=1.0):
    return {
        "position": {"x": x, "y": y, "z": z},
        "rotation": {"x": rx, "y": ry, "z": rz, "w": rw},
    }


def main():
    parser = argparse.ArgumentParser(description="CineAnchor API Test Suite")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    client = APIClient(args.base_url)

    # ---- 启动检查 ----
    print("\n🔍 Checking if server is running...")
    try:
        urlopen(f"{args.base_url}/health", timeout=5)
    except Exception as e:
        print(f"❌ Cannot connect to {args.base_url}: {e}")
        print("   Start the server first: python main.py")
        sys.exit(1)

    # ---- 测试套件 ----
    render_mode = client.test_health()
    client.test_root()

    scenes = client.test_list_scenes()
    test_scene = scenes[0] if scenes else "test_scene"

    # 场景管理
    client.test_create_scene(test_scene)
    client.test_create_scene_invalid()

    # 相机录制 — 模拟 dolly-in 推近镜头
    poses = [
        make_pose(0, 0, -5),
        make_pose(0, 0.05, -4),
        make_pose(0, 0.1, -3),
    ]
    for i, pose in enumerate(poses):
        client.test_record_frame(test_scene, i, pose)

    client.test_record_frame_missing_scene()

    # 视频渲染
    client.test_render_video(test_scene, "A cinematic dolly-in shot, dramatic lighting, 8K", fps=24)
    client.test_render_video_no_depth_maps()

    # 清理
    client.test_clear_data(test_scene)

    # ---- 结果 ----
    ok = client.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
