import os
import sys
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

from app.config import MODELS_DIR, VIDEOS_DIR, DEPTH_DIR, RENDER_MODE
from app.database import init_db
from app.scene_manager import (
    create_scene, check_and_update_scene, get_scene, list_scenes,
    create_scene_with_blender,
)
from app.camera_path import (
    save_camera_path, get_camera_path, list_camera_paths, delete_camera_path
)
from app.depth_renderer import render_depth_maps, render_preview_video
from app.camera_presets import list_presets

# --- 初始化数据库 ---
init_db()

# --- 渲染引擎检测 ---
render_mode: str = "unknown"
render_service: object = None

def _init_render_service():
    global render_mode, render_service

    try:
        from real_3dgs import Real3DGS
        service = Real3DGS("test_scene.ply")
        render_mode = "real_3dgs"
        render_service = service
        print(f"[CineAnchor] Render mode: REAL_3DGS (GPU)")
        return
    except FileNotFoundError:
        print("[CineAnchor] PLY file not found, falling back to simulated mode.")
    except Exception as e:
        print(f"[CineAnchor] Real3DGS unavailable: {e}")
        print("[CineAnchor] Falling back to simulated mode.")

    from simulated_3dgs import Simulated3DGS
    render_mode = "simulated_3dgs"
    render_service = Simulated3DGS()
    print(f"[CineAnchor] Render mode: SIMULATED_3DGS (CPU/Mock)")

# --- FastAPI App ---
app = FastAPI(title="CineAnchor API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_init_render_service()

from video_renderer import VideoRenderer
video_renderer = VideoRenderer()

# --- 静态文件 ---
app.mount("/static", StaticFiles(directory="static", html=True), name="static")
app.mount("/static/models", StaticFiles(directory=str(MODELS_DIR)), name="models")
app.mount("/depth_maps", StaticFiles(directory=str(DEPTH_DIR)), name="depth_maps")
app.mount("/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")
app.mount("/docs", StaticFiles(directory="docs", html=True), name="docs")

# --- 全局录制状态 ---
recorded_camera_frames: dict = {}
recorded_depth_map_paths: dict = {}

# --- Pydantic 模型 ---

class GenerateSceneRequest(BaseModel):
    prompt: str

class SaveCameraPathRequest(BaseModel):
    scene_id: str
    name: str = "Untitled"
    duration: float = 5.0
    fps: int = 24
    camera_mode: str = "orbit"
    interpolation: str = "catmull-rom"
    keyframes: list[dict] = []

class CameraPose(BaseModel):
    position: dict
    rotation: dict

class RecordFrameRequest(BaseModel):
    scene_id: str
    frame_id: int
    camera_pose: CameraPose

class RenderVideoRequest(BaseModel):
    scene_id: str
    prompt: str
    fps: int = 12
    interpolation: int = 3
    conditioning_scale: float = 1.9
    num_steps: int = 28
    seed: int = 42

# ============================================================
# 状态
# ============================================================
@app.get("/", summary="首页")
async def root():
    return RedirectResponse("/static/index.html")

@app.get("/health")
async def health():
    cuda_ok = False
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
    except Exception:
        pass
    return {
        "status": "ok",
        "render_mode": render_mode,
        "platform": sys.platform,
        "cuda_available": cuda_ok,
    }

# ============================================================
# 3D 场景生成 (Meshy API)
# ============================================================
@app.post("/api/scenes/generate", summary="Text-to-3D 生成")
async def generate_scene(req: GenerateSceneRequest):
    """提交 Meshy Text-to-3D 生成任务"""
    result = create_scene(req.prompt)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/scenes/generate-blender", summary="Blender 本地生成 3D 场景")
async def api_generate_scene_blender(req: GenerateSceneRequest):
    """使用 Blender 本地生成 3D 场景 (无需外部 API，离线可用)"""
    result = create_scene_with_blender(req.prompt)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/api/scenes", summary="场景列表")
async def api_list_scenes(status: str = None):
    return {"scenes": list_scenes(status)}

@app.get("/api/scenes/{scene_id}", summary="场景详情")
async def api_get_scene(scene_id: str):
    scene = get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    return scene

@app.post("/api/scenes/{scene_id}/check", summary="检查生成状态")
async def api_check_scene(scene_id: str):
    """检查并更新 Meshy 任务状态"""
    result = check_and_update_scene(scene_id)
    if "error" in result and "不存在" in result["error"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

# ============================================================
# 取景器 (保留兼容旧 API)
# ============================================================
@app.get("/scenes", summary="旧版场景列表")
async def old_list_scenes():
    if render_mode == "simulated_3dgs":
        scenes = render_service.scenes
        return {
            "render_mode": render_mode,
            "scenes": {k: v["description"] for k, v in scenes.items()}
        }
    return {
        "render_mode": render_mode,
        "scenes": {"test_scene": "Real 3DGS scene loaded from PLY file"}
    }

@app.post("/scene/create", summary="旧版创建场景")
async def old_create_scene(scene_id: str):
    if render_mode == "simulated_3dgs":
        if scene_id not in render_service.scenes:
            available = list(render_service.scenes.keys())
            raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found. Available: {available}")
    elif render_mode == "real_3dgs":
        if scene_id != "test_scene":
            raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found. Available: ['test_scene']")
    else:
        raise HTTPException(status_code=500, detail=f"Unknown render mode: {render_mode}")

    recorded_camera_frames[scene_id] = []
    recorded_depth_map_paths[scene_id] = []
    return {"scene_id": scene_id, "render_mode": render_mode}

@app.post("/camera/record_frame", summary="旧版录制帧")
async def old_record_frame(request: RecordFrameRequest):
    scene_id = request.scene_id
    frame_id = request.frame_id
    camera_pose = request.camera_pose.model_dump()

    if scene_id not in recorded_camera_frames:
        raise HTTPException(status_code=400, detail=f"Scene '{scene_id}' not initialized.")

    try:
        depth_map_path = render_service.render_depth_map(
            scene_id=scene_id, camera_pose=camera_pose, frame_id=frame_id
        )
        recorded_camera_frames[scene_id].append({
            "frame_id": frame_id, "camera_pose": camera_pose, "depth_map_path": depth_map_path
        })
        recorded_depth_map_paths[scene_id].append(depth_map_path)
        depth_map_url = f"/depth_maps/{os.path.basename(depth_map_path)}"
        return {"message": f"Frame {frame_id} recorded.", "depth_map_path": depth_map_path, "depth_map_url": depth_map_url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/render/video", summary="旧版渲染视频")
async def old_render_video(request: RenderVideoRequest):
    scene_id = request.scene_id
    if scene_id not in recorded_depth_map_paths or not recorded_depth_map_paths[scene_id]:
        raise HTTPException(status_code=400, detail=f"No depth maps recorded for scene '{scene_id}'.")

    depth_map_list = recorded_depth_map_paths[scene_id]
    try:
        video_filepath = video_renderer.render_pipeline(
            depth_map_paths=depth_map_list, prompt=request.prompt,
            scene_id=scene_id, fps=request.fps,
            interpolation=request.interpolation,
            conditioning_scale=request.conditioning_scale,
            num_steps=request.num_steps, seed=request.seed,
        )
        recorded_camera_frames.pop(scene_id, None)
        recorded_depth_map_paths.pop(scene_id, None)
        video_url = f"/videos/{os.path.basename(video_filepath)}"
        return {"video_url": video_url, "message": "Video rendering completed."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/clear_data/{scene_id}", summary="旧版清空数据")
async def old_clear_data(scene_id: str):
    if scene_id in recorded_camera_frames:
        recorded_camera_frames.pop(scene_id)
    if scene_id in recorded_depth_map_paths:
        for path in recorded_depth_map_paths.pop(scene_id, []):
            if os.path.exists(path):
                os.remove(path)
    for d in [DEPTH_DIR, VIDEOS_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
            os.makedirs(d, exist_ok=True)
    return {"message": f"All data for scene '{scene_id}' cleared."}

# ============================================================
# Camera Path CRUD API
# ============================================================
@app.post("/api/camera-paths", summary="保存 Camera Path")
async def api_save_camera_path(req: SaveCameraPathRequest):
    result = save_camera_path(
        scene_id=req.scene_id,
        name=req.name,
        duration=req.duration,
        fps=req.fps,
        camera_mode=req.camera_mode,
        interpolation=req.interpolation,
        keyframes=req.keyframes,
    )
    return result

@app.get("/api/camera-paths", summary="Camera Path 列表")
async def api_list_camera_paths(scene_id: str = None):
    return {"paths": list_camera_paths(scene_id)}

@app.get("/api/camera-paths/{path_id}", summary="Camera Path 详情")
async def api_get_camera_path(path_id: str):
    path = get_camera_path(path_id)
    if not path:
        raise HTTPException(status_code=404, detail="Camera path 不存在")
    return path

@app.put("/api/camera-paths/{path_id}", summary="更新 Camera Path")
async def api_update_camera_path(path_id: str, req: SaveCameraPathRequest):
    existing = get_camera_path(path_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Camera path 不存在")
    result = save_camera_path(
        scene_id=req.scene_id,
        name=req.name,
        duration=req.duration,
        fps=req.fps,
        camera_mode=req.camera_mode,
        interpolation=req.interpolation,
        keyframes=req.keyframes,
        path_id=path_id,
    )
    return result

@app.delete("/api/camera-paths/{path_id}", summary="删除 Camera Path")
async def api_delete_camera_path(path_id: str):
    if not delete_camera_path(path_id):
        raise HTTPException(status_code=404, detail="Camera path 不存在")
    return {"message": "已删除"}


# ============================================================
# Depth Map Rendering API
# ============================================================
@app.post("/api/camera-paths/{path_id}/render-depth", summary="渲染深度图")
async def api_render_depth(path_id: str):
    """为已保存的 camera path 渲染真实深度图序列"""
    result = render_depth_maps(path_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/camera-paths/{path_id}/render-preview", summary="预览运镜")
async def api_render_preview(path_id: str):
    """直接渲染 GLB 场景预览视频 (EEVEE, 无 AI, 秒出)"""
    result = render_preview_video(path_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ============================================================
# Demo / Presets API
# ============================================================
@app.get("/api/demo/setup", summary="Demo 模式初始化")
async def api_demo_setup():
    """返回已有场景 + Demo 运镜路径，供 Demo 模式一键加载"""
    scenes = list_scenes("ready")
    if not scenes:
        raise HTTPException(status_code=404, detail="没有可用的场景，请先生成一个场景")

    scene = scenes[0]
    scene_id = scene["id"]

    existing = list_camera_paths(scene_id)
    demo_paths = [p for p in existing if p.get("name", "").startswith("[Demo]")]

    return {
        "scene_id": scene_id,
        "model_url": scene.get("model_url", ""),
        "scene_prompt": scene.get("user_prompt", ""),
        "template": scene.get("template", ""),
        "paths": [
            {"id": p["id"], "name": p["name"], "keyframe_count": len(p.get("keyframes", []))}
            for p in demo_paths
        ],
    }


@app.get("/api/camera-presets", summary="镜头预设列表")
async def api_list_presets():
    return {"presets": list_presets()}




# --- 运行 ---
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
