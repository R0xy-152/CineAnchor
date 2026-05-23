"""Convert EXR depth frames to normalized 0-255 PNG.
Reads EXR files rendered by Blender, normalizes each frame, saves as PNG.
"""
import cv2
import numpy as np
from pathlib import Path
import os

DEMO_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "demo_depth_frames"

for scene_dir in sorted(DEMO_DIR.iterdir()):
    if not scene_dir.is_dir():
        continue

    exr_frames = sorted(scene_dir.glob("frame_*.exr"))
    if not exr_frames:
        continue

    scene_name = scene_dir.name
    print(f"\n{scene_name}: {len(exr_frames)} EXR frames")

    # Collect all depth values for global normalization (optional, but consistent)
    all_depths = []
    for f in exr_frames:
        depth = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
        if depth is not None:
            all_depths.append(depth)

    if not all_depths:
        print("  No valid frames, skipping")
        continue

    # Global percentile for consistent normalization across frames
    all_vals = np.concatenate([d.ravel() for d in all_depths])
    v_min = np.percentile(all_vals[all_vals < 1e10], 2)
    v_max = np.percentile(all_vals[all_vals < 1e10], 98)
    if v_max - v_min < 0.001:
        v_min, v_max = all_vals[all_vals < 1e10].min(), all_vals[all_vals < 1e10].max()

    print(f"  Global range: [{v_min:.3f}, {v_max:.3f}]")

    good_frames = 0
    for depth, exr_f in zip(all_depths, exr_frames):
        depth_norm = np.clip((depth - v_min) / (v_max - v_min) * 255, 0, 255).astype(np.uint8)
        png_path = str(exr_f).replace('.exr', '.png')
        cv2.imwrite(png_path, depth_norm)

        uniq = len(np.unique(depth_norm))
        if uniq > 10:
            good_frames += 1

        # Remove EXR
        os.remove(str(exr_f))

    print(f"  {good_frames}/{len(all_depths)} frames with structure (unique>10)")

print("\nDone! EXR → PNG normalized.")
