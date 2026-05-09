"""
CineAnchor Frame Interpolator
==============================
帧插值：在已有 RGB 帧之间插入中间帧，平滑视频运动。

GPU 路径: RAFT 光流 + 双向扭曲 (torchvision >= 0.15)
CPU 降级: Crossfade 混合 (纯 numpy)

用法:
    interp = FrameInterpolator()
    smoother = interp.interpolate_sequence(frame_paths, multiplier=3, output_dir="smoothed/")
"""

import os
import numpy as np
from PIL import Image


class FrameInterpolator:
    """帧插值器，自动检测最佳可用方法"""

    def __init__(self):
        self.mode = self._detect_mode()
        self._raft_model = None

    def _detect_mode(self) -> str:
        """检测可用的插值方法: raft > crossfade"""
        try:
            import torch
            from torchvision.models.optical_flow import raft_large
            if torch.cuda.is_available():
                _ = raft_large(pretrained=False)
                return "raft"
        except Exception:
            pass
        return "crossfade"

    # ---- 主入口 ----

    def interpolate_sequence(self, frame_paths: list[str],
                             multiplier: int = 3,
                             output_dir: str = "interpolated_frames") -> list[str]:
        """
        在帧序列之间插入中间帧。

        Args:
            frame_paths: 输入帧路径列表 (N 帧)
            multiplier: 插值倍数 (3 → 每对之间插入 2 帧)
            output_dir: 输出目录

        Returns:
            插值后的帧路径列表 (~N*multiplier 帧)
        """
        if len(frame_paths) < 2:
            return frame_paths

        os.makedirs(output_dir, exist_ok=True)

        if self.mode == "raft":
            return self._interpolate_raft(frame_paths, multiplier, output_dir)
        return self._interpolate_crossfade(frame_paths, multiplier, output_dir)

    # ---- Crossfade 插值 (CPU, 无依赖) ----

    def _interpolate_crossfade(self, frame_paths, multiplier, output_dir):
        """线性混合插值：简单但能平滑硬切"""
        frames = [np.array(Image.open(p).convert("RGB"), dtype=np.float32)
                  for p in frame_paths]

        h, w = frames[0].shape[:2]
        result_paths = []

        for i in range(len(frames)):
            if i < len(frames) - 1:
                result_paths.extend(
                    self._blend_pair(frames[i], frames[i + 1], i, multiplier,
                                     output_dir, h, w)
                )
            else:
                # 最后一帧
                out = os.path.join(output_dir, f"frame_{i * multiplier:04d}.png")
                Image.fromarray(frames[i].astype(np.uint8)).save(out)
                result_paths.append(out)

        print(f"[FrameInterpolator] Crossfade: {len(frame_paths)} → "
              f"{len(result_paths)} frames ({multiplier}x)")
        return result_paths

    def _blend_pair(self, f0, f1, pair_idx, multiplier, output_dir, h, w):
        """在一对帧之间生成 multiplier 帧 (含首帧)"""
        paths = []
        for j in range(multiplier):
            t = j / multiplier
            blended = ((1 - t) * f0 + t * f1).astype(np.uint8)
            out_idx = pair_idx * multiplier + j
            out = os.path.join(output_dir, f"frame_{out_idx:04d}.png")
            Image.fromarray(blended).save(out)
            paths.append(out)
        return paths

    # ---- RAFT 光流插值 (GPU) ----

    def _interpolate_raft(self, frame_paths, multiplier, output_dir):
        """基于 RAFT 光流的运动补偿插值"""
        import torch
        import torchvision.transforms.functional as TF

        device = torch.device("cuda")

        frames = []
        for p in frame_paths:
            img = Image.open(p).convert("RGB")
            tensor = TF.to_tensor(img).unsqueeze(0).to(device)  # [1, 3, H, W]
            frames.append(tensor)

        if self._raft_model is None:
            from torchvision.models.optical_flow import raft_large
            self._raft_model = raft_large(
                pretrained=True, progress=False
            ).to(device).eval()

        result_paths = []

        for i in range(len(frames)):
            if i < len(frames) - 1:
                result_paths.extend(
                    self._raft_blend_pair(frames[i], frames[i + 1], i,
                                          multiplier, output_dir, device)
                )
            else:
                out = os.path.join(output_dir, f"frame_{i * multiplier:04d}.png")
                self._save_tensor(frames[i], out)
                result_paths.append(out)

        print(f"[FrameInterpolator] RAFT: {len(frame_paths)} → "
              f"{len(result_paths)} frames ({multiplier}x)")
        return result_paths

    def _raft_blend_pair(self, f0, f1, pair_idx, multiplier, output_dir, device):
        """RAFT 双向流 + 扭曲混合"""
        import torch
        import torch.nn.functional as F

        paths = []
        # 保存首帧
        out0 = os.path.join(output_dir, f"frame_{pair_idx * multiplier:04d}.png")
        self._save_tensor(f0, out0)
        paths.append(out0)

        # 计算从 f0→f1 和 f1→f0 的双向光流
        with torch.no_grad():
            flow_fwd = self._raft_model(f0 * 255, f1 * 255)[-1]   # f0→f1
            flow_bwd = self._raft_model(f1 * 255, f0 * 255)[-1]   # f1→f0

        _, _, h, w = f0.shape

        for j in range(1, multiplier):
            t = j / multiplier

            # 时间 t 的近似流: f0→t ≈ t * flow_fwd,  f1→t ≈ (1-t) * flow_bwd 反方向
            flow_0t = t * flow_fwd
            flow_1t = (1 - t) * (-flow_bwd)

            # 从 f0 扭曲到 t
            grid_0 = self._flow_to_grid(flow_0t, h, w, device)
            warped_0 = F.grid_sample(f0, grid_0, mode="bilinear",
                                     padding_mode="border", align_corners=True)

            # 从 f1 扭曲到 t
            grid_1 = self._flow_to_grid(flow_1t, h, w, device)
            warped_1 = F.grid_sample(f1, grid_1, mode="bilinear",
                                     padding_mode="border", align_corners=True)

            # 时间加权混合 + 遮挡权重
            weight_0 = 1 - t
            weight_1 = t
            blended = weight_0 * warped_0 + weight_1 * warped_1
            blended = torch.clamp(blended, 0, 1)

            out = os.path.join(output_dir,
                               f"frame_{pair_idx * multiplier + j:04d}.png")
            self._save_tensor(blended, out)
            paths.append(out)

        return paths

    @staticmethod
    def _flow_to_grid(flow, h, w, device):
        """将光流 [1,2,H,W] 转为 grid_sample 的 grid [1,H,W,2]"""
        import torch
        y, x = torch.meshgrid(
            torch.arange(h, device=device, dtype=torch.float32),
            torch.arange(w, device=device, dtype=torch.float32),
            indexing="ij"
        )
        # squeeze batch dim: flow[0] → [2, H, W]
        fx = flow[0, 0]  # [H, W]
        fy = flow[0, 1]  # [H, W]
        # 归一化到 [-1, 1]
        x = 2.0 * (x + fx) / (w - 1) - 1.0
        y = 2.0 * (y + fy) / (h - 1) - 1.0
        return torch.stack([x, y], dim=-1).unsqueeze(0)

    @staticmethod
    def _save_tensor(tensor, path):
        """将 [1,3,H,W] tensor 存为 PNG"""
        import torchvision.transforms.functional as TF
        img = tensor.squeeze(0).cpu()
        TF.to_pil_image(img).save(path)


# ---- 独立运行 ----
if __name__ == "__main__":
    import sys

    interpolator = FrameInterpolator()
    print(f"Interpolation mode: {interpolator.mode}")

    # 找已有 RGB 帧
    search_dirs = ["controlnet_output/e2e_frames",
                   "controlnet_output",
                   "videos/_frames"]
    frames = []
    for d in search_dirs:
        if os.path.isdir(d):
            found = sorted([os.path.join(d, f) for f in os.listdir(d)
                           if f.endswith(".png")])
            if found:
                frames = found
                break

    if not frames:
        print("No frames found. Run e2e_test.py first.")
        sys.exit(1)

    print(f"Found {len(frames)} frames in {os.path.dirname(frames[0])}")
    result = interpolator.interpolate_sequence(frames, multiplier=3,
                                                output_dir="interpolated_frames")
    print(f"Output: {len(result)} interpolated frames → interpolated_frames/")
