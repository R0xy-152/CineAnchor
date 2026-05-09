import os
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles # New import for serving static files
from pydantic import BaseModel
from typing import List, Dict
import uvicorn
import json

from real_3dgs import Real3DGS
from simulated_diffusion import SimulatedDiffusionRenderer

# --- FastAPI 应用初始化 ---
app = FastAPI(title="CineAnchor API", description="API for controlled AI video generation with 3D spatial anchors.")

# --- 初始化真实渲染引擎 ---
# 在 MVP 阶段，我们假设有一个 test_scene.ply 在根目录下
real_3dgs_service = Real3DGS("test_scene.ply")
simulated_diffusion_service = SimulatedDiffusionRenderer()

# --- 挂载静态文件目录 ---
# 注意：确保这些目录存在，并且是相对于 CineAnchor 项目根目录的路径
# 例如，如果你的深度图和视频输出在 CineAnchor/simulated_depth_maps 和 CineAnchor/simulated_videos
app.mount("/depth_maps", StaticFiles(directory=real_3dgs_service.output_dir), name="depth_maps")
app.mount("/videos", StaticFiles(directory=simulated_diffusion_service.output_dir), name="videos")


# --- 全局变量用于存储录制的帧和深度图路径 ---
# 注意：在实际生产环境中，这些应该存储在数据库或更持久的存储中
recorded_camera_frames: Dict[str, List[Dict]] = {}
recorded_depth_map_paths: Dict[str, List[str]] = {}

# --- Pydantic 模型定义 ---
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

class SceneCreateResponse(BaseModel):
    scene_id: str
    description: str

class RenderVideoResponse(BaseModel):
    video_url: str
    message: str


# --- API 路由 ---

@app.get("/", summary="Root", tags=["Status"])
async def read_root():
    return {"message": "Welcome to CineAnchor API!"}

@app.post("/scene/create", response_model=SceneCreateResponse, summary="Create a simulated 3DGS scene", tags=["Scene Management"])
async def create_scene(scene_id: str):
    """
    创建或选择一个模拟的 3DGS 场景。
    在 MVP 阶段，我们只是验证 scene_id 是否存在于预设场景中。
    """
    if scene_id != "test_scene":
        # MVP 阶段我们硬编码只支持一个测试场景
        raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found. Available scenes: ['test_scene']")
    
    description = "A real 3D Gaussian Splatting scene loaded from PLY."
    recorded_camera_frames[scene_id] = [] # 初始化帧列表
    recorded_depth_map_paths[scene_id] = [] # 初始化深度图路径列表
    return {"scene_id": scene_id, "description": description}

@app.post("/camera/record_frame", summary="Record camera pose and generate depth map", tags=["Camera Control"])
async def record_camera_frame(request: RecordFrameRequest):
    """
    接收前端发送的摄像机姿态，并触发模拟深度图渲染。
    """
    scene_id = request.scene_id
    frame_id = request.frame_id
    camera_pose = request.camera_pose.model_dump()

    if scene_id not in recorded_camera_frames:
        raise HTTPException(status_code=400, detail=f"Scene '{scene_id}' not initialized. Call /scene/create first.")

    # 使用真实的 3DGS 引擎渲染深度图
    try:
        depth_map_path = real_3dgs_service.render_depth_map(
            scene_id=scene_id,
            camera_pose=camera_pose,
            frame_id=frame_id
        )
        recorded_camera_frames[scene_id].append({"frame_id": frame_id, "camera_pose": camera_pose, "depth_map_path": depth_map_path})
        recorded_depth_map_paths[scene_id].append(depth_map_path)
        
        # 返回可访问的深度图 URL
        depth_map_url = f"http://localhost:8000/depth_maps/{os.path.basename(depth_map_path)}"
        return {"message": f"Frame {frame_id} recorded and depth map generated.", "depth_map_path": depth_map_path, "depth_map_url": depth_map_url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/render/video", response_model=RenderVideoResponse, summary="Render video from recorded depth maps and prompt", tags=["Video Rendering"])
async def render_video(request: RenderVideoRequest):
    """
    利用录制的深度图序列和语义 Prompt，触发模拟视频渲染。
    """
    scene_id = request.scene_id
    prompt = request.prompt
    fps = request.fps

    if scene_id not in recorded_depth_map_paths or not recorded_depth_map_paths[scene_id]:
        raise HTTPException(status_code=400, detail=f"No depth maps recorded for scene '{scene_id}'. Record frames first.")

    depth_map_list = recorded_depth_map_paths[scene_id]

    try:
        video_filepath = simulated_diffusion_service.render_video(
            depth_map_paths=depth_map_list,
            prompt=prompt,
            scene_id=scene_id,
            fps=fps
        )
        # 清理当前场景的录制数据，为下一次录制做准备
        recorded_camera_frames.pop(scene_id, None)
        recorded_depth_map_paths.pop(scene_id, None)

        # 返回可访问的视频 URL
        video_url = f"http://localhost:8000/videos/{os.path.basename(video_filepath)}"""
        return {"video_url": video_url, "message": "Video rendering simulated successfully."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/clear_data/{scene_id}", summary="Clear recorded data for a scene", tags=["Scene Management"])
async def clear_scene_data(scene_id: str):
    if scene_id in recorded_camera_frames:
        recorded_camera_frames.pop(scene_id)
    if scene_id in recorded_depth_map_paths:
        for path in recorded_depth_map_paths[scene_id]:
            if os.path.exists(path):
                os.remove(path) # 删除模拟的深度图文件
        recorded_depth_map_paths.pop(scene_id)
    
    # 清理模拟视频目录
    video_output_path = simulated_diffusion_service.output_dir
    if os.path.exists(video_output_path):
        shutil.rmtree(video_output_path) # 删除所有模拟视频文件
        os.makedirs(video_output_path, exist_ok=True)

    # 清理真实深度图目录
    depth_output_path = real_3dgs_service.output_dir
    if os.path.exists(depth_output_path):
        shutil.rmtree(depth_output_path) # 删除所有模拟深度图文件
        os.makedirs(depth_output_path, exist_ok=True)

    return {"message": f"All recorded data and simulated outputs for scene '{scene_id}' cleared."}

# --- 运行 FastAPI 应用 (仅在直接运行时调用) ---
if __name__ == "__main__":
    # 在 WSL 中，可以直接运行，但外部访问可能需要配置端口转发
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
