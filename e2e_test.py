"""
CineAnchor 端到端测试
====================
完整验证管线：PLY → 深度图序列 → ControlNet RGB 帧 → MP4 视频

SDXL 模式 (默认): 768×768, ControlNet-depth-sdxl-1.0-small, 逐帧+RAFT插值
SD 1.5 模式: 512×512, AnimateDiff 时序注意力

用法 (需要 NVIDIA GPU):
    python e2e_test.py           # SDXL 模式 (默认)
    python e2e_test.py --sd15    # SD 1.5 + AnimateDiff

前置条件:
    1. python generate_cube_splat.py   # 生成 test_scene.ply
    2. 所有依赖已安装 (requirements.txt)
"""

import os
import sys
import shutil
import numpy as np

# ============================================================
# 配置: SDXL vs SD 1.5
# ============================================================
USE_SDXL = "--sd15" not in sys.argv

if USE_SDXL:
    RESOLUTION = 768
    MODE_LABEL = "SDXL"
    PROMPT = (
        "A sharp geometric cube with clearly visible faces and crisp edges, "
        "floating in dark empty space. Studio lighting from the side creates "
        "strong highlights and deep shadows across the cube faces. "
        "High contrast, matte surface texture, photorealistic render, 8K."
    )
else:
    RESOLUTION = 512
    MODE_LABEL = "SD 1.5 + AnimateDiff"
    PROMPT = ("a sharp-edged geometric cube with visible faces and clear boundaries, "
              "floating in dark space, studio lighting, high contrast, photorealistic, "
              "crisp edges, matte surface")


def generate_camera_trajectory(num_frames: int = 8):
    """Dolly-in 推近轨迹：相机从 z=7 匀速推进到 z=4.0"""
    poses = []
    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)
        z = 7.0 * (1 - t) + 4.0 * t
        poses.append({
            "position": {"x": 0.0, "y": 0.0, "z": z},
            "rotation": {"x": 0.0, "y": 1.0, "z": 0.0, "w": 0.0}
        })
    return poses


def main():
    print("=" * 60)
    print(f"  CineAnchor — E2E Pipeline Test [{MODE_LABEL}]")
    print(f"  Resolution: {RESOLUTION}×{RESOLUTION}")
    print("=" * 60)

    # ---- Step 0: 清理旧输出 ----
    for d in ["real_depth_maps", "controlnet_output", "videos"]:
        if os.path.isdir(d):
            shutil.rmtree(d)
            print(f"  Cleaned: {d}/")

    # ---- Step 0: 检查 PLY ----
    for candidate in ["scene_textured_cube.ply", "scene_complex.ply", "test_scene.ply"]:
        if os.path.exists(candidate):
            ply_path = candidate
            print(f"  Using: {ply_path}")
            break
    else:
        print("ERROR: No PLY found. Run: python generate_cube_splat.py")
        sys.exit(1)

    # ---- Step 1: 深度图渲染 (全局归一化) ----
    print(f"\n[1/4] Rendering depth maps ({RESOLUTION}×{RESOLUTION})...")
    from real_3dgs import Real3DGS
    renderer = Real3DGS(ply_path)

    poses = generate_camera_trajectory(num_frames=8)
    print(f"  Camera: {len(poses)} frames, dolly-in z=7→4.0")
    print(f"  Near/far clip: {renderer.near_plane}/{renderer.far_plane}")

    depth_map_paths = renderer.render_depth_maps_batch(
        "test_scene", poses,
        width=RESOLUTION, height=RESOLUTION
    )
    print(f"  Generated {len(depth_map_paths)} globally-normalized depth maps")

    # ---- Step 2: ControlNet RGB 帧 ----
    print(f"\n[2/4] Generating RGB frames via ControlNet-Depth [{MODE_LABEL}]...")
    from controlnet_renderer import ControlNetRenderer

    if USE_SDXL:
        cn_renderer = ControlNetRenderer(use_sdxl=True, sdxl_resolution=RESOLUTION)
    else:
        cn_renderer = ControlNetRenderer()

    frame_dir = "controlnet_output/e2e_frames"
    depth_paths = sorted([
        os.path.join(renderer.output_dir, f) for f in os.listdir(renderer.output_dir)
        if f.endswith(".png")
    ])

    try:
        cn_renderer.render_animated(
            depth_paths, PROMPT, frame_dir,
            num_inference_steps=25, seed=42,
            controlnet_conditioning_scale=1.7,
        )
    except Exception as e:
        print(f"  render_animated failed ({e}), falling back to render_batch")
        cn_renderer.render_batch(renderer.output_dir, PROMPT, frame_dir,
                                 num_inference_steps=25, seed=42,
                                 controlnet_conditioning_scale=1.7)

    # ---- Step 3: 帧插值 (RAFT 光流, 平滑帧间过渡) ----
    print("\n[3/4] Interpolating frames (RAFT ×3)...")
    from frame_interpolator import FrameInterpolator
    interpolator = FrameInterpolator()
    print(f"  Interpolation mode: {interpolator.mode}")

    frame_paths = sorted([
        os.path.join(frame_dir, f) for f in os.listdir(frame_dir)
        if f.endswith(".png")
    ])

    if not frame_paths:
        print("ERROR: No RGB frames generated!")
        sys.exit(1)

    interp_dir = "controlnet_output/e2e_interpolated"
    frame_paths = interpolator.interpolate_sequence(
        frame_paths, multiplier=3, output_dir=interp_dir
    )

    # ---- Step 4: ffmpeg 视频合成 ----
    print("\n[4/4] Stitching frames into video...")
    from video_renderer import VideoRenderer
    vr = VideoRenderer()

    output = vr.stitch(frame_paths, "videos/e2e_test_output.mp4", fps=8)

    print("\n" + "=" * 60)
    print(f"  E2E Test Complete [{MODE_LABEL}]")
    print(f"  Output: {output}")
    print(f"  Frames: {len(frame_paths)} (3x interpolated)")
    print("=" * 60)


if __name__ == "__main__":
    main()
