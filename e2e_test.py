"""
CineAnchor 端到端测试
====================
完整验证 Phase 1 管线：PLY → 深度图序列 → ControlNet RGB 帧 → MP4 视频

用法 (需要 NVIDIA GPU):
    python e2e_test.py

前置条件:
    1. python generate_cube_splat.py   # 生成 test_scene.ply
    2. 所有依赖已安装 (requirements.txt)
"""

import os
import sys
import numpy as np


def generate_camera_trajectory(num_frames: int = 8):
    """
    生成 dolly-in 推近轨迹：相机从 z=8 匀速推进到 z=2。
    所有相机朝向原点 (0,0,0)，使用 OpenCV 约定 (Z-forward)。
    """
    poses = []
    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)
        z = 8.0 * (1 - t) + 2.0 * t  # 8 → 2
        # 四元数 (0, 1, 0, 0) = 绕 Y 轴 180°，让相机从 +Z 看向原点
        poses.append({
            "position": {"x": 0.0, "y": 0.0, "z": z},
            "rotation": {"x": 0.0, "y": 1.0, "z": 0.0, "w": 0.0}
        })
    return poses


def main():
    print("=" * 60)
    print("  CineAnchor — End-to-End Pipeline Test")
    print("=" * 60)

    # ---- Step 0: 检查 PLY ----
    ply_path = "test_scene.ply"
    if not os.path.exists(ply_path):
        print(f"ERROR: {ply_path} not found. Run: python generate_cube_splat.py")
        sys.exit(1)

    # ---- Step 1: 深度图渲染 (全局归一化) ----
    print("\n[1/3] Rendering depth maps with global normalization...")
    from real_3dgs import Real3DGS
    renderer = Real3DGS(ply_path)

    poses = generate_camera_trajectory(num_frames=8)
    print(f"  Camera trajectory: {len(poses)} frames (dolly-in: z=8 → z=2)")

    depth_map_paths = renderer.render_depth_maps_batch("test_scene", poses)
    print(f"  Generated {len(depth_map_paths)} globally-normalized depth maps")

    # ---- Step 2: ControlNet 批量渲染 ----
    print("\n[2/3] Generating RGB frames via ControlNet-Depth...")
    from controlnet_renderer import ControlNetRenderer
    cn_renderer = ControlNetRenderer()

    prompt = "a colorful cube floating in dark space, studio lighting, high quality"
    frame_dir = "controlnet_output/e2e_frames"
    cn_renderer.render_batch(renderer.output_dir, prompt, frame_dir,
                             num_inference_steps=20,
                             controlnet_conditioning_scale=0.85)

    # ---- Step 3: ffmpeg 视频合成 ----
    print("\n[3/3] Stitching frames into video...")
    from video_renderer import VideoRenderer
    vr = VideoRenderer()

    frame_paths = sorted([
        os.path.join(frame_dir, f) for f in os.listdir(frame_dir)
        if f.endswith(".png")
    ])

    if not frame_paths:
        print("ERROR: No RGB frames generated!")
        sys.exit(1)

    output = vr.stitch(frame_paths, "videos/e2e_test_output.mp4", fps=8)

    print("\n" + "=" * 60)
    print(f"  ✅ End-to-End Test Complete!")
    print(f"  Output: {output}")
    print(f"  Frames: {len(frame_paths)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
