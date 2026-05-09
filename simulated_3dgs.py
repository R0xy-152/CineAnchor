"""
Simulated 3DGS 渲染器 — macOS 开发用
=====================================
使用简单几何体（球体、立方体、平面）的距离场模拟深度图渲染。
相机位置和方向的变化会产生真实的视差和遮挡效果。

场景定义: 球体 + 立方体 + 背景平面
深度计算: 逐像素射线与场景求交 (简化光线步进)
"""

import numpy as np
import os
from PIL import Image
from typing import Optional


# ============================================================
# 基础工具：四元数 → 旋转矩阵
# ============================================================

def _quat_to_rot(q: dict) -> np.ndarray:
    """四元数 → 3x3 旋转矩阵 (Hamilton convention)"""
    x, y, z, w = q["x"], q["y"], q["z"], q["w"]
    return np.array([
        [1 - 2*y*y - 2*z*z,     2*x*y - 2*w*z,     2*x*z + 2*w*y],
        [2*x*y + 2*w*z,         1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
        [2*x*z - 2*w*y,         2*y*z + 2*w*x,     1 - 2*x*x - 2*y*y]
    ], dtype=np.float32)


# ============================================================
# 场景定义：简单几何体的距离场
# ============================================================

class SimpleScene:
    """使用 SDF (Signed Distance Functions) 定义的简化场景"""

    def __init__(self, objects: list[dict], background_depth: float = 20.0):
        """
        Args:
            objects: 几何体列表，每个元素为 {"type": "sphere"|"box"|"plane", ...}
            background_depth: 背景深度（无物体命中时的默认值）
        """
        self.objects = objects
        self.background_depth = background_depth

    def sdf(self, point: np.ndarray) -> np.ndarray:
        """计算点云的场景 SDF (最小距离)"""
        d = np.full(point.shape[0], np.inf)
        for obj in self.objects:
            d = np.minimum(d, _sdf_for_object(obj, point))
        return d

    def ray_march_depth(
        self,
        cam_pos: np.ndarray,
        ray_dirs: np.ndarray,
        max_dist: float = 50.0,
        steps: int = 64
    ) -> np.ndarray:
        """
        简化光线步进：对每个像素的射线，找到第一个物体交点距离。

        Args:
            cam_pos:  [3] 相机世界坐标
            ray_dirs: [H, W, 3] 每个像素的射线方向 (归一化)
            max_dist: 最大追踪距离
            steps:    步进次数

        Returns:
            depth: [H, W] 深度图，无交点处为 background_depth
        """
        h, w = ray_dirs.shape[:2]
        depth = np.full((h, w), self.background_depth, dtype=np.float32)

        for _ in range(steps):
            current = cam_pos + ray_dirs * depth[..., None]
            current_flat = current.reshape(-1, 3)
            d = self.sdf(current_flat).reshape(h, w)

            # 命中判定 (距离 < 0.05 视为到达表面)
            hit = d < 0.05
            depth = np.where(hit, depth, depth + np.where(d > 0, d, 0))

        return depth


def _sdf_sphere(p: np.ndarray, center: np.ndarray, radius: float) -> np.ndarray:
    return np.linalg.norm(p - center, axis=-1) - radius


def _sdf_box(p: np.ndarray, center: np.ndarray, half_size: np.ndarray) -> np.ndarray:
    q = np.abs(p - center) - half_size
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + min(np.max(q, axis=-1), 0)


def _sdf_plane(p: np.ndarray, normal: np.ndarray, offset: float) -> np.ndarray:
    return np.dot(p, normal) + offset


def _sdf_for_object(obj: dict, p: np.ndarray) -> np.ndarray:
    t = obj["type"]
    if t == "sphere":
        return _sdf_sphere(p, np.array(obj["center"]), obj["radius"])
    elif t == "box":
        return _sdf_box(p, np.array(obj["center"]), np.array(obj["half_size"]))
    elif t == "plane":
        return _sdf_plane(p, np.array(obj["normal"]), obj["offset"])
    return np.full(p.shape[0], np.inf)


# ============================================================
# 预定义场景
# ============================================================

SCENE_DEFINITIONS = {
    "office_scene": {
        "description": "一个有桌椅的简单办公室，窗外是城市景观。",
        "objects": [
            {"type": "plane", "normal": [0, 1, 0], "offset": 1.5},        # 地板
            {"type": "plane", "normal": [0, 0, 1], "offset": 6.0},         # 后墙
            {"type": "box", "center": [0, 0.0, 0], "half_size": [1, 0.8, 2]},   # 桌子
            {"type": "sphere", "center": [0, 0.5, 0], "radius": 0.4},      # 桌上球体
            {"type": "box", "center": [2, -0.3, -0.5], "half_size": [0.3, 0.5, 0.3]}, # 椅子
            {"type": "box", "center": [-1.5, 0.3, -2], "half_size": [0.5, 0.8, 0.1]}, # 窗户
        ],
        "background_depth": 15.0,
    },
    "forest_path": {
        "description": "一条穿过茂密森林的小径，阳光从树叶间洒落。",
        "objects": [
            {"type": "plane", "normal": [0, 1, 0], "offset": 1.0},          # 地面
            # 两排树 (圆柱简化为细长立方体)
            {"type": "box", "center": [-2, 0.0, 2], "half_size": [0.3, 2, 0.3]},
            {"type": "box", "center": [2, 0.0, 2], "half_size": [0.3, 2, 0.3]},
            {"type": "box", "center": [-2.5, 0.0, -2], "half_size": [0.3, 2, 0.3]},
            {"type": "box", "center": [2.5, 0.0, -2], "half_size": [0.3, 2, 0.3]},
            # 远处的树
            {"type": "box", "center": [-3, 0.0, 5], "half_size": [0.35, 2.5, 0.35]},
            {"type": "box", "center": [3, 0.0, 5], "half_size": [0.35, 2.5, 0.35]},
        ],
        "background_depth": 30.0,
    },
    "test_scene": {
        "description": "简单测试场景：一个彩色立方体悬浮在空间中。",
        "objects": [
            {"type": "box", "center": [0, 0, 0], "half_size": [1, 1, 1]},
        ],
        "background_depth": 10.0,
    },
}


# ============================================================
# 渲染器
# ============================================================

class Simulated3DGS:
    def __init__(self, width: int = 512, height: int = 288, fov_y_deg: float = 60.0):
        """
        初始化模拟渲染器。

        Args:
            width, height: 渲染分辨率
            fov_y_deg:     垂直视场角
        """
        self.width = width
        self.height = height
        self.output_dir = "simulated_depth_maps"
        os.makedirs(self.output_dir, exist_ok=True)

        # 内参
        fov_y = fov_y_deg * np.pi / 180.0
        self.fy = (height / 2) / np.tan(fov_y / 2)
        self.fx = self.fy
        self.cx = width / 2
        self.cy = height / 2

        # 预计算像素射线方向 (相机空间)
        self._precompute_ray_dirs()

        # 场景缓存
        self._scene_cache: dict[str, SimpleScene] = {}
        self.scenes = SCENE_DEFINITIONS

    def _precompute_ray_dirs(self):
        """预计算每个像素在相机空间中的射线方向"""
        y, x = np.mgrid[0:self.height, 0:self.width]
        self._ray_dirs_cam = np.stack([
            (x - self.cx) / self.fx,
            -(y - self.cy) / self.fy,  # Y 轴翻转 (图像坐标系 → 相机坐标系)
            np.ones((self.height, self.width)),
        ], axis=-1).astype(np.float32)

        # 归一化
        norms = np.linalg.norm(self._ray_dirs_cam, axis=-1, keepdims=True)
        self._ray_dirs_cam /= norms

    def _get_scene(self, scene_id: str) -> SimpleScene:
        if scene_id not in self._scene_cache:
            if scene_id not in SCENE_DEFINITIONS:
                raise ValueError(f"Scene '{scene_id}' not found. Available: {list(SCENE_DEFINITIONS.keys())}")
            s = SCENE_DEFINITIONS[scene_id]
            self._scene_cache[scene_id] = SimpleScene(s["objects"], s["background_depth"])
        return self._scene_cache[scene_id]

    def _camera_to_world_rays(self, camera_pose: dict) -> np.ndarray:
        """将相机空间的射线方向转换到世界空间"""
        rot = camera_pose["rotation"]
        R = _quat_to_rot(rot)  # Camera → World 旋转矩阵

        # 射线方向: R @ d_cam
        h, w = self._ray_dirs_cam.shape[:2]
        dirs_cam_flat = self._ray_dirs_cam.reshape(-1, 3)
        dirs_world_flat = (R @ dirs_cam_flat.T).T
        return dirs_world_flat.reshape(h, w, 3)

    def render_depth_map(
        self,
        scene_id: str,
        camera_pose: dict,
        frame_id: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> str:
        """
        根据相机姿态渲染深度图。

        Args:
            scene_id:    场景 ID (office_scene / forest_path / test_scene)
            camera_pose: {"position": {x,y,z}, "rotation": {x,y,z,w}}
            frame_id:    帧编号
            width, height: 可选覆盖分辨率

        Returns:
            保存的深度图 PNG 文件路径
        """
        if scene_id not in SCENE_DEFINITIONS:
            raise ValueError(f"Scene '{scene_id}' not found. Available: {list(SCENE_DEFINITIONS.keys())}")

        scene = self._get_scene(scene_id)

        pos = camera_pose["position"]
        cam_pos = np.array([pos["x"], pos["y"], pos["z"]], dtype=np.float32)

        # 世界空间中的射线方向
        ray_dirs = self._camera_to_world_rays(camera_pose)

        # 光线步进计算深度
        raw_depth = scene.ray_march_depth(cam_pos, ray_dirs)

        # 归一化到 0-255
        d_min, d_max = raw_depth.min(), raw_depth.max()
        if d_max > d_min:
            normalized = (raw_depth - d_min) / (d_max - d_min)
        else:
            normalized = np.zeros_like(raw_depth)

        normalized = (normalized * 255).astype(np.uint8)
        normalized = 255 - normalized  # 反相：近白远黑

        # 保存
        filename = f"{scene_id}_depth_frame_{frame_id:04d}.png"
        filepath = os.path.join(self.output_dir, filename)
        Image.fromarray(normalized).save(filepath)

        print(f"[Simulated3DGS] Depth map saved: {filepath} (cam @ {cam_pos})")
        return filepath

    def get_scene_description(self, scene_id: str) -> str:
        return SCENE_DEFINITIONS.get(scene_id, {}).get("description", "Unknown scene.")


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    renderer = Simulated3DGS()

    # 测试 1: office_scene, 正面视角
    pose1 = {
        "position": {"x": 0.0, "y": 0.0, "z": -4.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
    }
    renderer.render_depth_map("office_scene", pose1, 0)

    # 测试 2: office_scene, 侧面视角 (有视差变化)
    pose2 = {
        "position": {"x": 3.0, "y": 0.5, "z": -4.0},
        "rotation": {"x": 0.0, "y": 0.35, "z": 0.0, "w": 0.94},  # 略向左看
    }
    renderer.render_depth_map("office_scene", pose2, 1)

    # 测试 3: forest_path
    pose3 = {
        "position": {"x": 0.0, "y": 0.0, "z": -3.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
    }
    renderer.render_depth_map("forest_path", pose3, 0)

    print("\nDone. All three depth maps should show different depths depending on camera pose.")
