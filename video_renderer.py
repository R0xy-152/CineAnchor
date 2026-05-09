"""
CineAnchor Video Renderer
=========================
Frame-to-video stitching via ffmpeg + unified rendering pipeline.
Auto-detects ControlNet (GPU) vs simulated (CPU) frame generation.
"""

import os
import sys
import subprocess
import numpy as np
from PIL import Image


class VideoRenderer:
    """ffmpeg 视频合成器 + 渲染管线编排"""

    def __init__(self, output_dir: str = "videos"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    @property
    def ffmpeg_available(self) -> bool:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # ---- ffmpeg 帧合成 ----

    def stitch(self, frame_paths: list[str], output_path: str,
               fps: int = 24, crf: int = 23) -> str:
        """将 PNG 帧序列合成为 MP4 视频"""
        if not frame_paths:
            raise ValueError("No frame paths provided")

        if not self.ffmpeg_available:
            return self._frames_fallback(frame_paths, output_path, fps)

        concat_file = os.path.join(self.output_dir, "_concat.txt")
        with open(concat_file, "w") as f:
            for p in frame_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-vf", "fps={},scale=512:512:force_original_aspect_ratio=decrease,"
                   "pad=512:512:(ow-iw)/2:(oh-ih)/2".format(fps),
            "-c:v", "libx264", "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        os.remove(concat_file)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        size_kb = os.path.getsize(output_path) / 1024
        print(f"Video rendered: {output_path} ({size_kb:.0f} KB, {fps} fps)")
        return output_path

    def _frames_fallback(self, frame_paths, output_path, fps):
        """无 ffmpeg 时：将帧复制到输出目录，保存为序列"""
        fallback_dir = output_path.replace(".mp4", "_frames")
        os.makedirs(fallback_dir, exist_ok=True)
        for i, src in enumerate(frame_paths):
            dst = os.path.join(fallback_dir, f"frame_{i:04d}.png")
            Image.open(src).save(dst)
        print(f"ffmpeg not available. Frames saved to: {fallback_dir}")
        print("Install ffmpeg: brew install ffmpeg  (macOS)")
        print("                  winget install ffmpeg  (Windows)")
        return fallback_dir

    # ---- 帧生成 ----

    def _generate_frames(self, depth_map_paths: list[str], prompt: str) -> list[str]:
        """根据深度图序列生成 RGB 帧。优先使用 ControlNet (GPU)，否则降级到模拟。"""
        # 尝试 GPU ControlNet
        controlnet = self._init_controlnet()
        if controlnet is not None:
            return self._generate_controlnet_frames(controlnet, depth_map_paths, prompt)

        # 降级：模拟帧生成
        return self._generate_simulated_frames(depth_map_paths)

    def _init_controlnet(self):
        """检测 GPU 并尝试导入 ControlNetRenderer"""
        try:
            import torch
            if not torch.cuda.is_available():
                return None
            from controlnet_renderer import ControlNetRenderer
            return ControlNetRenderer()
        except Exception as e:
            print(f"[VideoRenderer] ControlNet not available: {e}")
            return None

    def _generate_controlnet_frames(self, controlnet, depth_map_paths, prompt):
        """使用 ControlNet 逐帧生成 RGB。优先尝试 AnimateDiff 时序模式。"""
        frame_dir = os.path.join(self.output_dir, "_frames")
        os.makedirs(frame_dir, exist_ok=True)

        # 尝试 AnimateDiff 时序一致性生成
        try:
            if len(depth_map_paths) >= 2:
                return controlnet.render_animated(
                    depth_map_paths, prompt, frame_dir,
                    num_inference_steps=25, seed=42,
                    controlnet_conditioning_scale=1.3,
                )
        except Exception as e:
            print(f"[VideoRenderer] AnimateDiff unavailable ({e}), "
                  f"falling back to per-frame render")

        # 降级: 逐帧独立生成
        frame_paths = []
        for i, depth_path in enumerate(depth_map_paths):
            out_path = os.path.join(frame_dir, f"rgb_frame_{i:04d}.png")
            controlnet.render_rgb(
                depth_path, prompt, out_path,
                controlnet_conditioning_scale=1.0,
            )
            frame_paths.append(out_path)

        return frame_paths

    def _generate_simulated_frames(self, depth_map_paths):
        """模拟帧生成：将深度图着色为 RGB 帧（灰度 → 彩色热力图）"""
        frame_dir = os.path.join(self.output_dir, "_frames")
        os.makedirs(frame_dir, exist_ok=True)

        frame_paths = []
        for i, depth_path in enumerate(depth_map_paths):
            depth = np.array(Image.open(depth_path).convert("L"), dtype=np.float32)

            # 归一化深度 → 彩色热力图
            d_min, d_max = depth.min(), depth.max()
            if d_max > d_min:
                depth_norm = (depth - d_min) / (d_max - d_min)
            else:
                depth_norm = depth

            # 蓝(近) → 青 → 绿 → 黄 → 红(远)
            r = (depth_norm * 255).astype(np.uint8)
            g = ((1 - abs(depth_norm - 0.5) * 2) * 255).astype(np.uint8)
            b = ((1 - depth_norm) * 255).astype(np.uint8)

            rgb = np.stack([r, g, b], axis=-1)
            out = os.path.join(frame_dir, f"rgb_frame_{i:04d}.png")
            Image.fromarray(rgb).resize((512, 512), Image.LANCZOS).save(out)
            frame_paths.append(out)

        print(f"[VideoRenderer] Generated {len(frame_paths)} simulated frames")
        return frame_paths

    # ---- 完整管线 ----

    def render_pipeline(self, depth_map_paths: list[str], prompt: str,
                        scene_id: str, fps: int = 24,
                        interpolation: int = 1) -> str:
        """深度图序列 → RGB 帧 → (插值) → MP4 视频（完整管线）

        Args:
            interpolation: 帧插值倍数。1=不插值, 3=每对插入2帧
        """
        if not depth_map_paths:
            raise ValueError("No depth maps provided")

        print(f"[VideoRenderer] Pipeline start: {len(depth_map_paths)} frames, "
              f"prompt='{prompt[:50]}...', fps={fps}, interpolation={interpolation}x")

        # Step 1: 帧生成
        frame_paths = self._generate_frames(depth_map_paths, prompt)

        # Step 2: 帧插值 (可选)
        if interpolation > 1:
            from frame_interpolator import FrameInterpolator
            interp = FrameInterpolator()
            interp_dir = os.path.join(self.output_dir, "_interpolated")
            frame_paths = interp.interpolate_sequence(
                frame_paths, multiplier=interpolation, output_dir=interp_dir
            )

        # Step 3: 视频合成
        video_name = (f"{scene_id}_{len(frame_paths)}frames_{fps}fps"
                      + (f"_x{interpolation}" if interpolation > 1 else "")
                      + ".mp4")
        video_path = os.path.join(self.output_dir, video_name)

        return self.stitch(frame_paths, video_path, fps)


# ---- 独立运行 ----
if __name__ == "__main__":
    renderer = VideoRenderer()

    print(f"ffmpeg available: {renderer.ffmpeg_available}")

    # 找深度图
    depth_dirs = ["real_depth_maps", "simulated_depth_maps"]
    depth_maps = []
    for d in depth_dirs:
        if os.path.isdir(d):
            depth_maps = sorted([
                os.path.join(d, f) for f in os.listdir(d)
                if f.endswith(".png")
            ])
            if depth_maps:
                break

    if not depth_maps:
        print("No depth maps found. Run real_3dgs.py or simulated_3dgs.py first.")
        sys.exit(1)

    print(f"Found {len(depth_maps)} depth map(s)")
    output = renderer.render_pipeline(
        depth_maps,
        prompt="a colorful cube floating in dark space, studio lighting, high quality",
        scene_id="test_scene",
        fps=8
    )
    print(f"Output: {output}")
