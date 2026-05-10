import os
import shutil
import sys
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn
import json

from video_renderer import VideoRenderer

# --- 渲染引擎自动检测 ---
# macOS 无 CUDA/gsplat → 降级到模拟模式
# Windows/Linux + NVIDIA → 使用真实 3DGS

render_mode: str = "unknown"
render_service: object = None

def _init_render_service():
    """检测环境并初始化可用的渲染引擎"""
    global render_mode, render_service

    # 1. 尝试真实 3DGS (需要 gsplat + CUDA)
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

    # 2. 降级到模拟 3DGS
    from simulated_3dgs import Simulated3DGS
    render_mode = "simulated_3dgs"
    render_service = Simulated3DGS()
    print(f"[CineAnchor] Render mode: SIMULATED_3DGS (CPU/Mock)")

# --- FastAPI 应用初始化 ---
app = FastAPI(title="CineAnchor API", description="API for controlled AI video generation with 3D spatial anchors.")

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_init_render_service()
video_renderer = VideoRenderer()

# --- 挂载静态文件目录 ---
app.mount("/static", StaticFiles(directory="static", html=True), name="static")
app.mount("/depth_maps", StaticFiles(directory=render_service.output_dir), name="depth_maps")
app.mount("/videos", StaticFiles(directory=video_renderer.output_dir), name="videos")


# --- 全局变量 ---
recorded_camera_frames: Dict[str, List[Dict]] = {}
recorded_depth_map_paths: Dict[str, List[str]] = {}

# --- Pydantic 模型 ---
class CameraPose(BaseModel):
    position: Dict[str, float]
    rotation: Dict[str, float]

class RecordFrameRequest(BaseModel):
    scene_id: str
    frame_id: int
    camera_pose: CameraPose

class RenderVideoRequest(BaseModel):
    scene_id: str
    prompt: str
    fps: int = 24
    interpolation: int = 1  # 帧插值倍数: 1=不插, 3=3x帧率
    conditioning_scale: float = 1.7  # ControlNet 注入强度
    num_steps: int = 25              # 推理步数
    seed: int = 42                   # 随机种子

class HealthResponse(BaseModel):
    status: str
    render_mode: str
    platform: str
    cuda_available: bool


# --- API 路由 ---

@app.get("/", summary="Root", tags=["Status"])
async def read_root():
    return RedirectResponse("/static/viewfinder.html")

@app.get("/health", response_model=HealthResponse, summary="Health check with render capability", tags=["Status"])
async def health():
    """报告服务健康状态和当前渲染能力"""
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

@app.get("/scenes", summary="List available scenes", tags=["Scene Management"])
async def list_scenes():
    """列出当前可用的场景"""
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

@app.post("/scene/create", summary="Create/select a scene", tags=["Scene Management"])
async def create_scene(scene_id: str):
    """
    创建或选择一个 3DGS 场景。
    模拟模式下支持: office_scene, forest_path
    真实模式下当前仅支持: test_scene
    """
    if render_mode == "simulated_3dgs":
        if scene_id not in render_service.scenes:
            available = list(render_service.scenes.keys())
            raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found. Available: {available}")

    elif render_mode == "real_3dgs":
        if scene_id != "test_scene":
            raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found. Available: ['test_scene']")

    else:
        raise HTTPException(status_code=500, detail=f"Unknown render mode: {render_mode}")

    desc = render_service.scenes[scene_id]["description"] if render_mode == "simulated_3dgs" else \
        "A real 3D Gaussian Splatting scene loaded from PLY."

    recorded_camera_frames[scene_id] = []
    recorded_depth_map_paths[scene_id] = []
    return {"scene_id": scene_id, "description": desc, "render_mode": render_mode}

@app.post("/camera/record_frame", summary="Record camera pose and generate depth map", tags=["Camera Control"])
async def record_camera_frame(request: RecordFrameRequest):
    """
    接收前端发送的摄像机姿态，触发深度图渲染。
    """
    scene_id = request.scene_id
    frame_id = request.frame_id
    camera_pose = request.camera_pose.model_dump()

    if scene_id not in recorded_camera_frames:
        raise HTTPException(status_code=400, detail=f"Scene '{scene_id}' not initialized. Call /scene/create first.")

    try:
        depth_map_path = render_service.render_depth_map(
            scene_id=scene_id,
            camera_pose=camera_pose,
            frame_id=frame_id
        )
        recorded_camera_frames[scene_id].append({"frame_id": frame_id, "camera_pose": camera_pose, "depth_map_path": depth_map_path})
        recorded_depth_map_paths[scene_id].append(depth_map_path)

        depth_map_url = f"/depth_maps/{os.path.basename(depth_map_path)}"
        return {"message": f"Frame {frame_id} recorded.", "depth_map_path": depth_map_path, "depth_map_url": depth_map_url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/render/video", summary="Render video from recorded depth maps and prompt", tags=["Video Rendering"])
async def render_video(request: RenderVideoRequest):
    """
    利用录制的深度图序列和语义 Prompt，触发视频渲染。
    """
    scene_id = request.scene_id
    prompt = request.prompt
    fps = request.fps

    if scene_id not in recorded_depth_map_paths or not recorded_depth_map_paths[scene_id]:
        raise HTTPException(status_code=400, detail=f"No depth maps recorded for scene '{scene_id}'. Record frames first.")

    depth_map_list = recorded_depth_map_paths[scene_id]

    try:
        video_filepath = video_renderer.render_pipeline(
            depth_map_paths=depth_map_list,
            prompt=prompt,
            scene_id=scene_id,
            fps=fps,
            interpolation=request.interpolation,
            conditioning_scale=request.conditioning_scale,
            num_steps=request.num_steps,
            seed=request.seed,
        )
        recorded_camera_frames.pop(scene_id, None)
        recorded_depth_map_paths.pop(scene_id, None)

        video_url = f"/videos/{os.path.basename(video_filepath)}"
        return {"video_url": video_url, "message": "Video rendering completed."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/clear_data/{scene_id}", summary="Clear recorded data for a scene", tags=["Scene Management"])
async def clear_scene_data(scene_id: str):
    """清理场景的所有录制数据和产出文件"""
    if scene_id in recorded_camera_frames:
        recorded_camera_frames.pop(scene_id)
    if scene_id in recorded_depth_map_paths:
        for path in recorded_depth_map_paths.pop(scene_id, []):
            if os.path.exists(path):
                os.remove(path)

    for d in [render_service.output_dir, video_renderer.output_dir]:
        if os.path.exists(d):
            shutil.rmtree(d)
            os.makedirs(d, exist_ok=True)

    return {"message": f"All data for scene '{scene_id}' cleared."}


# --- 运行 ---
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
