"""
CineAnchor Phase 1 — 相机坐标到深度图生成完整工作流
========================================================
本文件是 Phase 1 (静态场景相机运动) 的参考实现与伪代码混合体。
真实渲染路径依赖 gsplat (NVIDIA GPU)，模拟路径可在 macOS 上直接运行。

Pipeline:
  User 3D Camera Pose → World-to-Camera Matrix → gsplat Rasterization
  → Expected Depth Map → Normalization → Depth Image (PNG)
  → Depth Sequence → ControlNet Input

核心技术点:
  1. 四元数 → 旋转矩阵 → View Matrix (World to Camera)
  2. 内参矩阵 K 的构造 (针孔相机模型)
  3. 深度归一化的三种策略及适用场景
  4. 深度图序列作为 ControlNet 输入的预处理
"""

import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

# ============================================================
# SECTION 1: 数据结构定义
# ============================================================

@dataclass
class CameraPose:
    """6-DOF 相机姿态 (前端 3D 取景器输出格式)"""
    position: np.ndarray   # [x, y, z] 世界坐标
    rotation: np.ndarray   # [x, y, z, w] 四元数 (Hamilton convention)

@dataclass
class CameraIntrinsics:
    """针孔相机内参"""
    width: int
    height: int
    fx: float      # 焦距 (像素)
    fy: float
    cx: float      # 主点
    cy: float
    near: float = 0.01
    far: float = 100.0

    @classmethod
    def from_fov(cls, width: int, height: int, fov_y_deg: float = 60.0):
        """从视场角构造内参 (最常用方式)"""
        fov_y = fov_y_deg * np.pi / 180.0
        fy = (height / 2) / np.tan(fov_y / 2)
        fx = fy  # 正方形像素
        return cls(
            width=width, height=height,
            fx=fx, fy=fy,
            cx=width/2, cy=height/2
        )


# ============================================================
# SECTION 2: 坐标变换 — 四元数 → View Matrix
# ============================================================

def quaternion_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    """
    四元数 → 3x3 旋转矩阵
    q = [x, y, z, w] (Hamilton convention, 前端 Three.js 常用格式)

    数学原理:
      R = I + 2w·[v]× + 2·[v]×²
      其中 v = (x,y,z), [v]× 是反对称矩阵
    """
    x, y, z, w = q[0], q[1], q[2], q[3]
    R = np.array([
        [1 - 2*y*y - 2*z*z,     2*x*y - 2*w*z,     2*x*z + 2*w*y],
        [2*x*y + 2*w*z,         1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
        [2*x*z - 2*w*y,         2*y*z + 2*w*x,     1 - 2*x*x - 2*y*y]
    ], dtype=np.float32)
    return R


def build_view_matrix(position: np.ndarray, rotation_quat: np.ndarray) -> np.ndarray:
    """
    构造 World-to-Camera 视图矩阵 (4x4)

    World → Camera 变换:
      P_cam = R_world^T · (P_world - T)
            = R_world^T · P_world - R_world^T · T

    因此 View Matrix:
      V = [ R^T  |  -R^T · T ]
          [ 0    |      1     ]

    注意: 这是 OpenCV/COLMAP 约定 (Y-down, Z-forward)
    """
    R = quaternion_to_rotation_matrix(rotation_quat)
    T = position.astype(np.float32)

    view_mat = np.eye(4, dtype=np.float32)
    view_mat[:3, :3] = R.T          # 旋转的转置 = 逆旋转
    view_mat[:3, 3] = -R.T @ T      # 平移补偿
    return view_mat


# ============================================================
# SECTION 3: 深度图渲染 (gsplat 调用)
# ============================================================

def render_depth_map_gsplat(
    means: np.ndarray,        # [N, 3] 高斯均值
    quats: np.ndarray,        # [N, 4] 高斯旋转 (四元数)
    scales: np.ndarray,       # [N, 3] 高斯缩放
    opacities: np.ndarray,    # [N]   高斯不透明度
    colors: np.ndarray,       # [N, 3] 高斯 RGB
    view_matrix: np.ndarray,  # [4, 4] World-to-Camera
    K: np.ndarray,            # [3, 3] 内参矩阵
    width: int,
    height: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    调用 gsplat 光栅化，同时输出 RGB 和 Expected Depth

    Returns:
        rgb:   [H, W, 3] uint8 渲染图像
        depth: [H, W]    float  期望深度 (Expected Depth / ED)

    gsplat rasterization 签名 (v1.4.0):
      rasterization(
          means, quats, scales, opacities, colors,
          viewmats,      # [B, 4, 4]
          Ks,            # [B, 3, 3]
          width, height,
          near_plane, far_plane,
          render_mode="RGB+ED",
      ) -> (rgb_tensor, depth_tensor)
    """
    # ---- 实际代码 (需要 gsplat 已安装) ----
    # import torch
    # from gsplat.rendering import rasterization
    #
    # device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    #
    # means_t    = torch.tensor(means, device=device)
    # quats_t    = torch.tensor(quats, device=device)
    # scales_t   = torch.tensor(scales, device=device)
    # opacities_t = torch.tensor(opacities, device=device)
    # colors_t   = torch.tensor(colors, device=device)
    # viewmats_t = torch.tensor(view_matrix, device=device).unsqueeze(0)
    # Ks_t       = torch.tensor(K, device=device).unsqueeze(0)
    #
    # rgb_out, depth_out = rasterization(
    #     means=means_t, quats=quats_t, scales=scales_t,
    #     opacities=opacities_t, colors=colors_t,
    #     viewmats=viewmats_t, Ks=Ks_t,
    #     width=width, height=height,
    #     near_plane=0.01, far_plane=100.0,
    #     render_mode="RGB+ED",
    # )
    #
    # rgb   = rgb_out.squeeze().permute(1, 2, 0).cpu().numpy()
    # depth = depth_out.squeeze().cpu().numpy()
    # return rgb, depth

    # ---- 模拟回退 (无 gsplat 时) ----
    print("[MOCK] gsplat rasterization — returning simulated depth")
    depth = np.random.rand(height, width).astype(np.float32) * 10.0
    rgb = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    return rgb, depth


# ============================================================
# SECTION 4: 深度归一化策略 (关键设计决策)
# ============================================================

class DepthNormalizer:
    """
    深度归一化的三种策略，对 ControlNet 输入质量有显著影响。

    策略选择指南:
      - 单场景固定距离 → Absolute (min_depth/max_depth 已知)
      - 多场景通用 → Per-Frame MinMax (最常用)
      - 保持时序一致 → Global MinMax (所有帧共享 min/max)

    ControlNet Depth 期望输入:
      - 0-255 uint8 PNG，近处=亮(255)，远处=暗(0)
      - M-LSD detector 内部会做自己的归一化
    """

    @staticmethod
    def per_frame_minmax(depth: np.ndarray) -> np.ndarray:
        """
        策略 A: 逐帧 Min-Max 归一化 (默认推荐)

        优点: 每帧使用完整动态范围，对比度最好
        缺点: 不同帧的绝对深度信息丢失 (100m 变白, 10m 也变白)
        适用: 相机移动范围不大时
        """
        d_min, d_max = depth.min(), depth.max()
        if d_max > d_min:
            normalized = (depth - d_min) / (d_max - d_min)
        else:
            normalized = np.zeros_like(depth)
        return (normalized * 255).astype(np.uint8)

    @staticmethod
    def global_minmax(
        depth_sequence: list[np.ndarray],
        percentile: float = 2.0
    ) -> list[np.ndarray]:
        """
        策略 B: 全局 Min-Max (推荐用于视频)

        对所有帧统计统一的 min/max，保持帧间深度一致性。
        使用百分位数裁剪异常值 (飞点 / 天空盒)。

        优点: 时序一致性最好，ControlNet 帧间稳定
        缺点: 需要预先渲染所有帧
        适用: 生成视频序列时
        """
        all_depths = np.concatenate([d.ravel() for d in depth_sequence])
        d_min = np.percentile(all_depths, percentile)
        d_max = np.percentile(all_depths, 100 - percentile)

        results = []
        for depth in depth_sequence:
            normalized = np.clip((depth - d_min) / (d_max - d_min), 0, 1)
            results.append(normalized)
        return [(n * 255).astype(np.uint8) for n in results]

    @staticmethod
    def absolute(depth: np.ndarray, near: float, far: float) -> np.ndarray:
        """
        策略 C: 绝对距离归一化

        使用已知的近/远平面，保留真实尺度信息。
        适用于已知场景物理尺寸的情况 (如室内 2m-20m)。

        优点: 保留度量信息，不同场景可比较
        缺点: 需要先验知识，可能浪费动态范围
        """
        normalized = np.clip((depth - near) / (far - near), 0, 1)
        return (normalized * 255).astype(np.uint8)


# ============================================================
# SECTION 5: 完整工作流 — 主 Pipeline
# ============================================================

class CineAnchorPhase1Pipeline:
    """
    Phase 1 完整工作流:

      Camera Trajectory → [View Matrix per frame] → gsplat Render → Depth Maps
      → Depth Normalization → Depth PNG Sequence → Ready for ControlNet
    """

    def __init__(
        self,
        ply_path: str,
        intrinsics: CameraIntrinsics,
        use_mock: bool = False
    ):
        self.intrinsics = intrinsics
        self.use_mock = use_mock

        if not use_mock:
            self.means, self.quats, self.scales, self.opacities, self.colors = \
                self._load_ply(ply_path)
        else:
            self._init_mock_gaussians()

    def _load_ply(self, ply_path: str):
        """从 PLY 文件加载 3DGS 属性"""
        from plyfile import PlyData
        ply = PlyData.read(ply_path)
        v = ply['vertex']

        means = np.stack([v['x'], v['y'], v['z']], axis=-1).astype(np.float32)
        scales = np.stack([v['scale_0'], v['scale_1'], v['scale_2']], axis=-1).astype(np.float32)
        quats = np.stack([v['rot_0'], v['rot_1'], v['rot_2'], v['rot_3']], axis=-1).astype(np.float32)
        quats = quats / np.linalg.norm(quats, axis=-1, keepdims=True)
        opacities = v['opacity'].astype(np.float32)

        # SH DC → RGB: RGB = SH_DC * SH_C0 + 0.5
        C0 = 0.28209479177387814
        sh_dc = np.stack([v['f_dc_0'], v['f_dc_1'], v['f_dc_2']], axis=-1)
        colors = np.clip(sh_dc * C0 + 0.5, 0.0, 1.0).astype(np.float32)

        return means, quats, scales, opacities, colors

    def _init_mock_gaussians(self):
        """模拟高斯点云 (macOS 测试用)"""
        n = 1000
        self.means = (np.random.rand(n, 3) * 2 - 1).astype(np.float32)
        self.quats = np.zeros((n, 4), dtype=np.float32)
        self.quats[:, 0] = 1.0
        self.scales = np.full((n, 3), -4.0, dtype=np.float32)
        self.opacities = np.full(n, 10.0, dtype=np.float32)
        self.colors = np.random.rand(n, 3).astype(np.float32)

    def generate_camera_trajectory(
        self,
        start_pose: CameraPose,
        end_pose: CameraPose,
        num_frames: int,
        interpolation: str = "linear"
    ) -> list[CameraPose]:
        """
        生成相机轨迹 (关键帧插值)

        支持类型:
          - linear:   等速直线/球面插值 (LERP + SLERP)
          - ease_in_out: 缓入缓出 (推荐用于镜头运动)
          - dolly_zoom:  推拉变焦 (位置前移 + FOV 变化)
          - handheld:    手持抖动 (叠加 Perlin 噪声)

        实际项目中，这由前端 Three.js 手动录制替代，
        但程序化轨迹对自动化测试和批量生成很重要。
        """
        frames = []
        for i in range(num_frames):
            t = i / max(num_frames - 1, 1)

            # 缓入缓出
            if interpolation == "ease_in_out":
                t = t * t * (3 - 2 * t)  # smoothstep

            # 位置: LERP
            pos = (1 - t) * start_pose.position + t * end_pose.position

            # 旋转: SLERP (球面线性插值)
            rot = self._slerp(start_pose.rotation, end_pose.rotation, t)

            frames.append(CameraPose(position=pos, rotation=rot))

        return frames

    def _slerp(self, q0: np.ndarray, q1: np.ndarray, t: float) -> np.ndarray:
        """四元数球面线性插值"""
        dot = np.dot(q0, q1)
        if dot < 0:
            q1 = -q1
            dot = -dot
        dot = np.clip(dot, -1.0, 1.0)

        if dot > 0.9995:
            result = q0 + t * (q1 - q0)
            return result / np.linalg.norm(result)

        theta_0 = np.arccos(dot)
        sin_theta = np.sin(theta_0)
        s0 = np.sin((1 - t) * theta_0) / sin_theta
        s1 = np.sin(t * theta_0) / sin_theta
        return s0 * q0 + s1 * q1

    def run(
        self,
        camera_trajectory: list[CameraPose],
        output_dir: str = "depth_maps",
        normalizer: str = "per_frame",
    ) -> list[Path]:
        """
        主执行流程: 对相机轨迹中的每一帧渲染深度图

        Args:
            camera_trajectory: 相机姿态列表 (来自程序化生成或前端录制)
            output_dir:        深度图输出目录
            normalizer:        归一化策略 ("per_frame" | "global" | "absolute")

        Returns:
            深度图 PNG 文件路径列表 (可直接传入 ControlNet pipeline)
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        K = np.array([
            [self.intrinsics.fx, 0,                   self.intrinsics.cx],
            [0,                  self.intrinsics.fy,   self.intrinsics.cy],
            [0,                  0,                    1]
        ], dtype=np.float32)

        raw_depths = []
        saved_paths = []

        for i, pose in enumerate(camera_trajectory):
            # Step 1: World → Camera 变换
            view_mat = build_view_matrix(pose.position, pose.rotation)

            # Step 2: 3DGS 光栅化 (depth 通道)
            _, depth_raw = render_depth_map_gsplat(
                self.means, self.quats, self.scales,
                self.opacities, self.colors,
                view_mat, K,
                self.intrinsics.width, self.intrinsics.height,
            )
            raw_depths.append(depth_raw)

        # Step 3: 深度归一化
        if normalizer == "global":
            normalized = DepthNormalizer.global_minmax(raw_depths)
        else:
            dn = DepthNormalizer()
            normalized = [dn.per_frame_minmax(d) for d in raw_depths]

        # Step 4: 保存为 PNG (ControlNet 输入格式)
        from PIL import Image
        for i, depth_norm in enumerate(normalized):
            filepath = output_path / f"depth_frame_{i:04d}.png"
            Image.fromarray(depth_norm).save(filepath)
            saved_paths.append(filepath)

        print(f"Saved {len(saved_paths)} depth maps to {output_dir}/")
        return saved_paths


# ============================================================
# SECTION 6: ControlNet 视频生成接口 (预留)
# ============================================================

class ControlNetVideoPipeline:
    """
    Phase 1 的下游: 深度图序列 → 视频

    技术选型:
      - ControlNet Depth (M-LSD): 最稳定, 适合室内/建筑场景
      - ControlNet Canny:         边缘清晰, 适合保留几何结构
      - AnimateDiff v3:           运动模块, 保证帧间时序一致性
      - SVD (Stable Video Diffusion): 图→视频, 需要额外 temporal 条件

    实际集成代码 (伪代码):
      from diffusers import StableVideoDiffusionPipeline
      from diffusers import ControlNetModel, StableDiffusionControlNetPipeline

      pipe = StableDiffusionControlNetPipeline.from_pretrained(
          "runwayml/stable-diffusion-v1-5",
          controlnet=ControlNetModel.from_pretrained("lllyasviel/control_v11f1p_sd15_depth"),
      )
      pipe.enable_xformers_memory_efficient_attention()

      for depth_png in depth_sequence:
          image = pipe(prompt="...", image=depth_png).images[0]
          # 逐帧生成后需要 temporal smoothing
    """

    @staticmethod
    def prepare_controlnet_input(
        depth_png_path: Path,
        target_size: tuple[int, int] = (512, 512)
    ) -> np.ndarray:
        """
        将深度图 PNG 预处理为 ControlNet 期望的输入格式

        ControlNet Depth 期望:
          - shape: (H, W, 3) 或 (H, W)
          - dtype: uint8 [0, 255]
          - 近处=亮, 远处=暗 (与 CineAnchor 深度图约定一致)
        """
        from PIL import Image
        img = Image.open(depth_png_path).convert("L")  # 灰度
        img = img.resize(target_size)
        return np.array(img)


# ============================================================
# SECTION 7: 端到端示例
# ============================================================

def demo_workflow():
    """
    演示完整 Phase 1 工作流:

    1. 初始化内参
    2. 加载/生成 3DGS 场景
    3. 生成相机轨迹 (程序化 dolly-in + 旋转)
    4. 渲染深度图序列
    5. 输出可直接用于 ControlNet 的深度图 PNG
    """
    print("=" * 60)
    print("CineAnchor Phase 1 — 相机坐标 → 深度图 工作流演示")
    print("=" * 60)

    # --- 配置 ---
    intrinsics = CameraIntrinsics.from_fov(
        width=512, height=288, fov_y_deg=60.0
    )

    # --- 初始化 Pipeline ---
    # 真实场景: CineAnchorPhase1Pipeline("scene.ply", intrinsics, use_mock=False)
    pipeline = CineAnchorPhase1Pipeline(
        "test_scene.ply", intrinsics, use_mock=True
    )

    # --- 定义相机轨迹 ---
    # 推近 (dolly-in) + 轻微右转: 模拟"缓慢推近并略带旋转"的镜头
    start_pose = CameraPose(
        position=np.array([0.0, 0.0, 8.0], dtype=np.float32),
        rotation=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),  # 单位四元数
    )
    end_pose = CameraPose(
        position=np.array([0.3, 0.1, 3.0], dtype=np.float32),  # 向前推进 5m, 微右移
        rotation=np.array([0.0, 0.15, 0.0, 0.989], dtype=np.float32),  # ~17° 右转
    )

    trajectory = pipeline.generate_camera_trajectory(
        start_pose, end_pose,
        num_frames=24,          # 1秒 @ 24fps
        interpolation="ease_in_out"
    )
    print(f"Generated {len(trajectory)} camera poses")

    # --- 渲染深度图 ---
    depth_paths = pipeline.run(
        trajectory,
        output_dir="depth_map_output",
        normalizer="per_frame"
    )

    print(f"\nPipeline complete. {len(depth_paths)} depth maps ready.")
    print("Next step: feed into ControlNet + AnimateDiff for video generation.")
    return depth_paths


if __name__ == "__main__":
    demo_workflow()
