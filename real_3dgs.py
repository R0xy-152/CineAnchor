import torch
import numpy as np
import os
from PIL import Image
from gsplat.rendering import rasterization

class Real3DGS:
    def __init__(self, ply_path: str):
        """
        初始化真实的 3DGS 渲染器。
        目前为了 MVP，我们假设所有场景共用这一个预加载的 PLY 模型。
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Initializing Real3DGS on device: {self.device}")
        
        # 加载 ply 文件（这里使用一个 mock，实际需要解析 ply 或 splat 文件）
        self.ply_path = ply_path
        self._load_ply(ply_path)
        
        self.output_dir = "real_depth_maps"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 预设摄像机内参 (MVP 阶段固定为 512x288, 模拟 16:9 比例)
        self.width = 512
        self.height = 288
        # 视场角 (Field of View)，假设为 60 度
        fov_y = 60.0 * np.pi / 180.0
        self.fy = (self.height / 2) / np.tan(fov_y / 2)
        self.fx = self.fy # 假设正方形像素
        self.cx = self.width / 2
        self.cy = self.height / 2

    def _load_ply(self, ply_path: str):
        """
        从真实的 3DGS PLY 文件加载高斯属性。
        """
        if not os.path.exists(ply_path):
            raise FileNotFoundError(f"PLY file '{ply_path}' not found!")
            
        print(f"Loading PLY from {ply_path}...")
        from plyfile import PlyData
        plydata = PlyData.read(ply_path)
        v = plydata['vertex']
        
        # 提取坐标
        xyz = np.stack([v['x'], v['y'], v['z']], axis=-1)
        self.means = torch.tensor(xyz, dtype=torch.float32, device=self.device)
        
        # 提取缩放
        scales = np.stack([v['scale_0'], v['scale_1'], v['scale_2']], axis=-1)
        self.scales = torch.tensor(scales, dtype=torch.float32, device=self.device)
        
        # 提取旋转
        rot = np.stack([v['rot_0'], v['rot_1'], v['rot_2'], v['rot_3']], axis=-1)
        self.quats = torch.tensor(rot, dtype=torch.float32, device=self.device)
        # 必须确保四元数归一化
        self.quats = self.quats / self.quats.norm(dim=-1, keepdim=True)
        
        # 提取不透明度
        opacities = v['opacity']
        self.opacities = torch.tensor(opacities, dtype=torch.float32, device=self.device)
        
        # 提取颜色 (SH 直流分量还原为 RGB)
        # SH_C0 = 0.28209479177387814
        # RGB = SH_DC * SH_C0 + 0.5
        sh_dc = np.stack([v['f_dc_0'], v['f_dc_1'], v['f_dc_2']], axis=-1)
        rgb = sh_dc * 0.28209479177387814 + 0.5
        # 防止越界并转为 gsplat 期望的 float 颜色
        rgb = np.clip(rgb, 0.0, 1.0)
        self.colors = torch.tensor(rgb, dtype=torch.float32, device=self.device)
            
        print(f"Successfully loaded {self.means.shape[0]} Gaussians into VRAM.")

    def _pose_to_view_matrix(self, camera_pose: dict) -> torch.Tensor:
        """
        修正：确保矩阵转换符合标准相机坐标系 (OpenCV惯例: z-forward, y-down, x-right)
        """
        pos = camera_pose["position"]
        rot = camera_pose["rotation"]
        
        # 1. 构造平移向量
        T = np.array([pos["x"], pos["y"], pos["z"]], dtype=np.float32)
        
        # 2. 构造旋转矩阵 (四元数转旋转矩阵)
        x, y, z, w = rot["x"], rot["y"], rot["z"], rot["w"]
        R = np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*w*z,     2*x*z + 2*w*y],
            [2*x*y + 2*w*z,     1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
            [2*x*z - 2*w*y,     2*y*z + 2*w*x,     1 - 2*x*x - 2*y*y]
        ], dtype=np.float32)
        
        # 3. 构造 View Matrix (World to Camera)
        # World to Camera: P_cam = R^T * (P_world - T) = R^T * P_world - R^T * T
        view_mat = np.eye(4, dtype=np.float32)
        view_mat[:3, :3] = R.T
        view_mat[:3, 3] = -R.T @ T
        
        return torch.tensor(view_mat, dtype=torch.float32, device=self.device)

    def render_depth_map(self, scene_id: str, camera_pose: dict, frame_id: int) -> str:
        """
        调用 gsplat 进行真实的光栅化渲染，并提取深度图。
        """
        view_matrix = self._pose_to_view_matrix(camera_pose)
        
        # 检查相机位置与场景中心的距离
        cam_pos = np.array([camera_pose["position"][k] for k in ["x", "y", "z"]])
        dist_to_origin = np.linalg.norm(cam_pos)
        print(f"[DEBUG] Camera distance to origin: {dist_to_origin:.2f}")
        
        # gsplat 需要内参矩阵 (3x3)
        K = torch.tensor([
            [self.fx, 0, self.cx],
            [0, self.fy, self.cy],
            [0, 0, 1]
        ], dtype=torch.float32, device=self.device)
        
        # 进行光栅化渲染！
        # 注意: gsplat 的 API 可能因版本而略有不同。我们目前使用其核心渲染函数。
        try:
            # 提取旋转和平移 (给 gsplat 使用的格式)
            viewmats = view_matrix.unsqueeze(0) # [1, 4, 4]
            Ks = K.unsqueeze(0) # [1, 3, 3]
            
            # TODO: 这里使用了 dummy 数据。如果是真实数据，需要进行 SH 到 RGB 的转换。
            # 为了 MVP 演示跑通，我们传入准备好的 tensors
            outputs = rasterization(
                means=self.means,
                quats=self.quats,
                scales=self.scales,
                opacities=self.opacities,
                colors=self.colors,
                viewmats=viewmats,
                Ks=Ks,
                width=self.width,
                height=self.height,
                near_plane=0.01,
                far_plane=100.0,
                render_mode="RGB+ED" # 告诉 gsplat 我们既要 RGB，也要 Expected Depth (ED)
            )
            
            # 提取深度图 (ED = Expected Depth)
            depth_data = outputs[1].squeeze().cpu().numpy()
            
            # [深度调试] 打印原始数值分布，看看物体到底在哪
            print(f"[DEBUG] Raw Depth min: {depth_data.min()}, max: {depth_data.max()}, mean: {depth_data.mean()}")
            
            # 自动归一化：不强制指定区间，先看看场景的真实深度分布
            d_min, d_max = depth_data.min(), depth_data.max()
            if d_max > d_min:
                normalized_depth = np.clip((depth_data - d_min) / (d_max - d_min), 0, 1)
            else:
                normalized_depth = np.zeros_like(depth_data)
                
            normalized_depth = (normalized_depth * 255).astype(np.uint8)
            normalized_depth = 255 - normalized_depth # 反相：近处为白，远处为黑

            # 构造输出路径
            filename = f"{scene_id}_real_depth_frame_{frame_id:04d}.png"
            filepath = os.path.join(self.output_dir, filename)

            # 保存为图片
            img = Image.fromarray(normalized_depth)
            img.save(filepath)

            print(f"Real depth map saved to: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"Error during gsplat rasterization: {e}")
            # 如果 gsplat 挂了，退回到生成纯色图，防止整个 API 崩溃
            filepath = os.path.join(self.output_dir, f"{scene_id}_error_depth_{frame_id:04d}.png")
            Image.fromarray(np.zeros((self.height, self.width), dtype=np.uint8)).save(filepath)
            return filepath

    def render_depth_maps_batch(self, scene_id: str,
                                 camera_poses: list[dict]) -> list[str]:
        """
        批量渲染深度图，使用全局百分位归一化确保帧间深度一致性。

        与逐帧 render_depth_map() 的关键区别：
        - 收集所有帧的原始深度 → 计算统一的 1%-99% 百分位 min/max
        - 所有帧用同一范围归一化 → 帧间不会出现深度漂移
        - ControlNet 看到稳定一致的几何输入 → 减少帧间扭曲
        """
        if not camera_poses:
            return []

        print(f"\n[BatchRender] Rendering {len(camera_poses)} frames with "
              f"GLOBAL depth normalization...")

        # Phase 1: 渲染所有帧，收集原始深度数据
        raw_depths = []
        for i, pose in enumerate(camera_poses):
            view_matrix = self._pose_to_view_matrix(pose)
            K = torch.tensor([
                [self.fx, 0, self.cx],
                [0, self.fy, self.cy],
                [0, 0, 1]
            ], dtype=torch.float32, device=self.device)

            outputs = rasterization(
                means=self.means,
                quats=self.quats,
                scales=self.scales,
                opacities=self.opacities,
                colors=self.colors,
                viewmats=view_matrix.unsqueeze(0),
                Ks=K.unsqueeze(0),
                width=self.width,
                height=self.height,
                near_plane=0.01,
                far_plane=100.0,
                render_mode="RGB+ED"
            )
            depth = outputs[1].squeeze().cpu().numpy()
            raw_depths.append(depth)
            print(f"  Frame {i}: raw depth [{depth.min():.3f}, {depth.max():.3f}] "
                  f"mean={depth.mean():.3f}")

        # Phase 2: 全局归一化 (1% / 99% 百分位裁剪飞点)
        all_depths = np.concatenate([d.ravel() for d in raw_depths])
        d_min = float(np.percentile(all_depths, 1))
        d_max = float(np.percentile(all_depths, 99))
        d_range = d_max - d_min
        if d_range <= 0:
            d_range = 1.0

        print(f"  Global depth range: [{d_min:.3f}, {d_max:.3f}] "
              f"(1-99 percentile)")

        # Phase 3: 统一归一化并保存
        paths = []
        for i, depth in enumerate(raw_depths):
            normalized = np.clip((depth - d_min) / d_range, 0, 1)
            normalized = ((1 - normalized) * 255).astype(np.uint8)  # 反相: 近白远黑

            filename = f"{scene_id}_real_depth_frame_{i:04d}.png"
            filepath = os.path.join(self.output_dir, filename)
            Image.fromarray(normalized).save(filepath)
            paths.append(filepath)

        print(f"  Saved {len(paths)} globally-normalized depth maps → "
              f"{self.output_dir}/\n")
        return paths


if __name__ == "__main__":
    renderer = Real3DGS("test_scene.ply")

    # 单帧测试
    test_pose = {
        "position": {"x": 0.0, "y": 0.0, "z": 5.0},
        "rotation": {"x": 0.0, "y": 1.0, "z": 0.0, "w": 0.0}
    }
    renderer.render_depth_map("test_scene", test_pose, 0)

    # 批量测试 (dolly-in 轨迹)
    print("\n--- Batch Render Test ---")
    poses = []
    for i in range(8):
        t = i / 7
        z = 7.0 * (1 - t) + 4.5 * t  # z≥4.5 避免面片饱和
        poses.append({
            "position": {"x": 0.0, "y": 0.0, "z": z},
            "rotation": {"x": 0.0, "y": 1.0, "z": 0.0, "w": 0.0}
        })
    renderer.render_depth_maps_batch("test_scene", poses)