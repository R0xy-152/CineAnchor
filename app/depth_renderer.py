"""
Blender 深度图渲染器

从 GLB 场景 + 相机运镜 → 渲染真实深度图 PNG

管线位置:
  prompt → GLB → 取景器 → 录制运镜 → [深度图] → ControlNet → 视频
"""

import subprocess
import json
import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from .config import BASE_DIR, DEPTH_DIR, MODELS_DIR, VIDEOS_DIR
from .database import db_session

# 自动检测 Blender 路径
def _find_blender() -> str:
    import platform
    if platform.system() == "Windows":
        blender = shutil.which("blender")
        if blender:
            return blender
        import glob as _glob
        for p in _glob.glob("C:/Program Files/Blender Foundation/Blender */blender.exe"):
            return p
        return "blender"
    elif platform.system() == "Darwin":
        candidates = ["/opt/homebrew/bin/blender", "/Applications/Blender.app/Contents/MacOS/blender"]
        for c in candidates:
            if os.path.exists(c):
                return c
        return shutil.which("blender") or "blender"
    else:
        return shutil.which("blender") or "blender"

BLENDER_BIN = _find_blender()
DEPTH_SCRIPT = BASE_DIR / "app" / "scenes" / "render_depth.py"


def _catmull_rom(p0, p1, p2, p3, t):
    """Catmull-Rom 插值 (四点)"""
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2 * p1) +
        (-p0 + p2) * t +
        (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
        (-p0 + 3 * p1 - 3 * p2 + p3) * t3
    )


def _interpolate_keyframes(keyframes: list[dict], fps: int) -> list[dict]:
    """
    将关键帧插值为逐帧相机位姿列表。
    使用 Catmull-Rom 插值，每对相邻关键帧之间填充 fps * (t2-t1) 帧。
    """
    if len(keyframes) < 2:
        return keyframes

    total_duration = keyframes[-1]["t"]
    total_frames = max(int(total_duration * fps), 1)

    frames = []
    for fi in range(total_frames + 1):
        t = fi / fps

        # 找到 t 所在的关键帧区间
        idx = 0
        for i, kf in enumerate(keyframes):
            if kf["t"] <= t:
                idx = i
            else:
                break

        if idx >= len(keyframes) - 1:
            # 已经超出最后一个关键帧
            kf = keyframes[-1]
            frames.append({"t": t, "pos": list(kf["pos"]), "quat": list(kf["quat"]), "fov": kf.get("fov", 55)})
            continue

        k0 = keyframes[max(0, idx - 1)]
        k1 = keyframes[idx]
        k2 = keyframes[min(len(keyframes) - 1, idx + 1)]
        k3 = keyframes[min(len(keyframes) - 1, idx + 2)]

        # 局部插值参数
        seg_start = k1["t"]
        seg_end = k2["t"]
        seg_duration = seg_end - seg_start
        if seg_duration < 0.001:
            local_t = 0.0
        else:
            local_t = (t - seg_start) / seg_duration

        # 对每个分量插值
        pos = [_catmull_rom(k0["pos"][i], k1["pos"][i], k2["pos"][i], k3["pos"][i], local_t) for i in range(3)]
        quat = [_catmull_rom(k0["quat"][i], k1["quat"][i], k2["quat"][i], k3["quat"][i], local_t) for i in range(4)]
        fov = _catmull_rom(
            k0.get("fov", 55), k1.get("fov", 55),
            k2.get("fov", 55), k3.get("fov", 55), local_t
        )

        # 归一化四元数
        qlen = math.sqrt(sum(v * v for v in quat))
        if qlen > 0.001:
            quat = [v / qlen for v in quat]

        frames.append({"t": t, "pos": pos, "quat": quat, "fov": fov})

    return frames


def _three_to_blender_pose(three_pos, three_target):
    """
    Three.js (Y-up) → Blender (Z-up) 坐标转换。
    直接转换 pos 和 target，不做四元数反推。
    """
    bx = three_pos[0]
    by = -three_pos[2]
    bz = three_pos[1]

    tx = three_target[0]
    ty = -three_target[2]
    tz = three_target[1]

    return (bx, by, bz), (tx, ty, tz)


def render_depth_maps(camera_path_id: str, output_dir: Optional[str] = None) -> dict:
    """
    为指定运镜渲染深度图。

    流程:
    1. 从 DB 获取 camera_path + scene
    2. 获取 GLB 模型路径
    3. 插值关键帧 → 逐帧相机位姿
    4. 转换坐标 Three.js → Blender
    5. 调用 Blender 渲染深度图
    6. 返回深度图路径列表
    """
    with db_session() as conn:
        path_row = conn.execute("SELECT * FROM camera_paths WHERE id = ?", (camera_path_id,)).fetchone()
        if not path_row:
            return {"error": f"Camera path {camera_path_id} 不存在"}

        scene_row = conn.execute("SELECT * FROM scenes WHERE id = ?", (path_row["scene_id"],)).fetchone()
        if not scene_row:
            return {"error": f"Scene {path_row['scene_id']} 不存在"}

        model_path = scene_row["model_path"]
        if not model_path or not os.path.exists(model_path):
            return {"error": f"模型文件不存在: {model_path}"}

    keyframes = json.loads(path_row["keyframes"])
    fps = path_row["fps"]

    # 插值
    frames = _interpolate_keyframes(keyframes, fps)
    print(f"[DepthRenderer] {len(keyframes)} keyframes → {len(frames)} frames @ {fps}fps")

    # 坐标转换
    blender_poses = []
    for f in frames:
        pos, target = _three_to_blender_pose(f["pos"], f.get("target", f["pos"]))
        blender_poses.append({
            "t": f["t"],
            "position": list(pos),
            "target": list(target),
            "fov": f.get("fov", 55),
        })

    # 输出目录
    out_dir = Path(output_dir) if output_dir else (DEPTH_DIR / f"depth_{camera_path_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 准备 Blender 输入
    render_input = {
        "glb_path": model_path,
        "output_dir": str(out_dir),
        "frames": blender_poses,
        "resolution_x": 768,
        "resolution_y": 512,
        "far_clip": 15.0,
        "engine": "CYCLES",
        "samples": 32,
    }

    input_path = Path(tempfile.gettempdir()) / f"cineanchor_depth_input_{camera_path_id}.json"
    input_path.write_text(json.dumps(render_input, ensure_ascii=False), encoding="utf-8")

    env = os.environ.copy()
    env["CINEANCHOR_ROOT"] = str(BASE_DIR)

    try:
        result = subprocess.run(
            [BLENDER_BIN, "--background", "--python", str(DEPTH_SCRIPT), "--", str(input_path)],
            capture_output=True, text=True, timeout=600,
            env=env, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            err = result.stderr[-800:] if result.stderr else "Unknown error"
            return {"error": f"Blender 深度渲染失败 (exit {result.returncode}): {err}"}
    except subprocess.TimeoutExpired:
        return {"error": "深度图渲染超时 (600s)"}
    finally:
        if input_path.exists():
            input_path.unlink()

    # ── 后处理: RGB → 灰度 (平均通道降噪) ──────────────────
    depth_files = sorted(out_dir.glob("frame_*.png"))
    if not depth_files:
        return {"error": f"未产出深度图文件: {out_dir}"}

    try:
        from PIL import Image
        import numpy as np
        for f in depth_files:
            img = Image.open(f)
            arr = np.array(img)
            if len(arr.shape) == 3 and arr.shape[2] >= 3:
                # 平均 RGB 通道 (降噪 + 保留深度变化)
                gray = arr[:, :, :3].mean(axis=2).astype(np.uint8)
            else:
                gray = arr
            Image.fromarray(gray).save(f)
    except ImportError:
        pass  # 如果没有 PIL, 保留原始 RGB PNG

    return {
        "camera_path_id": camera_path_id,
        "scene_id": path_row["scene_id"],
        "frame_count": len(depth_files),
        "depth_dir": str(out_dir),
        "depth_files": [str(f) for f in depth_files],
        "depth_urls": [f"/depth_maps/{out_dir.name}/{f.name}" for f in depth_files],
    }

PREVIEW_SCRIPT = BASE_DIR / "app" / "scenes" / "render_preview.py"


def render_preview_video(camera_path_id: str) -> dict:
    """直接渲染 GLB 场景预览视频 (无 AI, EEVEE 快速渲染)"""
    with db_session() as conn:
        path_row = conn.execute("SELECT * FROM camera_paths WHERE id = ?", (camera_path_id,)).fetchone()
        if not path_row:
            return {"error": f"Camera path {camera_path_id} 不存在"}

        scene_row = conn.execute("SELECT * FROM scenes WHERE id = ?", (path_row["scene_id"],)).fetchone()
        if not scene_row:
            return {"error": f"Scene {path_row['scene_id']} 不存在"}

        model_path = scene_row["model_path"]
        if not model_path or not os.path.exists(model_path):
            return {"error": f"模型文件不存在: {model_path}"}

    keyframes = json.loads(path_row["keyframes"])
    fps = path_row["fps"]

    frames = _interpolate_keyframes(keyframes, fps)
    print(f"[PreviewRender] {len(keyframes)} keyframes -> {len(frames)} frames @ {fps}fps")

    blender_poses = []
    for f in frames:
        pos, target = _three_to_blender_pose(f["pos"], f.get("target", f["pos"]))
        blender_poses.append({
            "t": f["t"],
            "position": list(pos),
            "target": list(target),
            "fov": f.get("fov", 55),
        })

    out_dir = DEPTH_DIR / f"preview_{camera_path_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("preview_*.png"):
        old.unlink()

    render_input = {
        "glb_path": model_path,
        "output_dir": str(out_dir),
        "frames": blender_poses,
        "resolution_x": 640,
        "resolution_y": 480,
        "engine": "CYCLES",
        "samples": 16,
    }

    input_path = Path(tempfile.gettempdir()) / f"cineanchor_preview_{camera_path_id}.json"
    input_path.write_text(json.dumps(render_input, ensure_ascii=False), encoding="utf-8")

    env = os.environ.copy()
    env["CINEANCHOR_ROOT"] = str(BASE_DIR)

    try:
        result = subprocess.run(
            [BLENDER_BIN, "--background", "--python", str(PREVIEW_SCRIPT), "--", str(input_path)],
            capture_output=True, text=True, timeout=600,
            env=env, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            err = result.stderr[-800:] if result.stderr else "Unknown error"
            return {"error": f"预览渲染失败 (exit {result.returncode}): {err}"}
    except subprocess.TimeoutExpired:
        return {"error": "预览渲染超时 (600s)"}
    finally:
        if input_path.exists():
            input_path.unlink()

    frame_files = sorted(out_dir.glob("preview_*.png"))
    if not frame_files:
        return {"error": f"未产出预览帧: {out_dir}"}

    from video_renderer import VideoRenderer
    preview_video = VIDEOS_DIR / f"preview_{camera_path_id}.mp4"
    vr = VideoRenderer()
    vr.stitch([str(f) for f in frame_files], str(preview_video), fps=fps)

    return {
        "camera_path_id": camera_path_id,
        "scene_id": path_row["scene_id"],
        "frame_count": len(frame_files),
        "video_url": f"/videos/preview_{camera_path_id}.mp4",
        "duration": len(frame_files) / fps,
    }
