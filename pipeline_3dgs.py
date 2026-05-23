"""
Full pipeline: PLY → 3DGS depth maps → ControlNet RGB → RAFT → MP4
Generates proper camera-motion depth maps from 3D Gaussian Splatting scenes.

Usage:
    python pipeline_3dgs.py                 # all 5 scenes
    python pipeline_3dgs.py --scene zen_garden  # single scene
"""
import os, sys, argparse, math, torch
import numpy as np
from pathlib import Path

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# ── Camera path generators ────────────────────────────────

def make_camera_path(scene_name, frames=24):
    """Generate camera poses for each scene. Returns list[dict]."""
    poses = []
    for i in range(frames):
        t = i / max(frames - 1, 1)
        if scene_name == "zen_garden":
            # Dolly-in: high right → center
            x = 8 * (1 - t)
            y = -6 * (1 - t)
            z = 5 - 2.5 * t
            look = np.array([0, 0, 0.5]) - np.array([x, y, z])
        elif scene_name == "scifi_corridor":
            # Walk through corridor
            x = 0.5 * (1 - t)
            y = 7 - 12 * t
            z = 1.0
            look = np.array([0, 0, 0.5]) - np.array([x, y, z])
        elif scene_name == "floating_islands":
            # Drone-like orbit
            angle = math.radians(-60 + 60 * t)
            r = 12
            x = r * math.cos(angle)
            y = -8 + 10 * t
            z = 8 - 4 * t
            look = np.array([0, 0, 3.5]) - np.array([x, y, z])
        elif scene_name == "desert_ruins":
            # Wide arc around pyramid
            angle = math.radians(-30 + 90 * t)
            r = 12 - 2 * t
            x = r * math.sin(angle)
            y = -8 + 6 * t
            z = 6 - 3 * t
            look = np.array([0, 0, 1.5]) - np.array([x, y, z])
        elif scene_name == "forest_glade":
            # Walk forward and up
            x = 6 * (1 - t)
            y = -6 + 7 * t
            z = 3 - 1.5 * t
            look = np.array([0, 0, 1.0]) - np.array([x, y, z])
        else:
            x, y, z = 8*(1-t), -6*(1-t), 5-3*t
            look = np.array([0, 0, 0.5]) - np.array([x, y, z])

        # Compute quaternion from look direction
        look = look / (np.linalg.norm(look) + 1e-8)
        # Simple quaternion from direction vector (assumes up=Z)
        up = np.array([0, 0, 1])
        right = np.cross(look, up)
        right = right / (np.linalg.norm(right) + 1e-8)
        up2 = np.cross(right, look)
        R = np.column_stack([right, up2, -look])
        # Matrix to quaternion
        w = math.sqrt(max(0, 1 + R[0,0] + R[1,1] + R[2,2])) / 2
        xq = (R[2,1] - R[1,2]) / (4 * w) if w > 1e-8 else 0
        yq = (R[0,2] - R[2,0]) / (4 * w) if w > 1e-8 else 0
        zq = (R[1,0] - R[0,1]) / (4 * w) if w > 1e-8 else 0

        poses.append({"position": {"x": x, "y": y, "z": z},
                       "rotation": {"x": xq, "y": yq, "z": zq, "w": w}})
    return poses


# ── Main pipeline ─────────────────────────────────────────

SCENES = [
    ("zen_garden",       "scene_zen_garden.ply",
     "a serene japanese zen garden with cherry blossoms, wooden bridge over pond, stone path, pine trees, golden hour lighting, photorealistic, masterpiece, sharp focus"),
    ("scifi_corridor",   "scene_scifi_corridor.ply",
     "a futuristic sci-fi corridor with neon blue lights, metallic walls, pillars, cyberpunk aesthetic, cinematic lighting, photorealistic, masterpiece"),
    ("floating_islands", "scene_floating_islands.ply",
     "floating islands in a fantasy sky, waterfalls cascading off edges, crystal formations, clouds, epic fantasy art, photorealistic, masterpiece"),
    ("desert_ruins",     "scene_desert_ruins.ply",
     "ancient egyptian desert ruins, a stone pyramid at center, stone columns and obelisks, sand dunes, harsh sunlight, cinematic, photorealistic, masterpiece"),
    ("forest_glade",     "scene_forest_glade.ply",
     "a sunny forest glade with giant ancient trees, moss covered ground, stone circle, god rays through canopy, nature, photorealistic, masterpiece"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=str, default=None)
    args = parser.parse_args()

    scenes = SCENES
    if args.scene:
        scenes = [(s, p, pr) for s, p, pr in SCENES if s == args.scene]
        if not scenes:
            print(f"Unknown scene: {args.scene}"); sys.exit(1)

    # Step 0: Generate PLY files
    print("=" * 60)
    print("  Step 0: Generating PLY files")
    print("=" * 60)
    from generate_cube_splat import (create_zen_garden_ply, create_scifi_corridor_ply,
                                      create_floating_islands_ply, create_desert_ruins_ply,
                                      create_forest_glade_ply)
    ply_generators = {
        "zen_garden": create_zen_garden_ply,
        "scifi_corridor": create_scifi_corridor_ply,
        "floating_islands": create_floating_islands_ply,
        "desert_ruins": create_desert_ruins_ply,
        "forest_glade": create_forest_glade_ply,
    }
    for scene_name, ply_path, _ in scenes:
        gen = ply_generators[scene_name]
        if not os.path.exists(ply_path):
            gen(ply_path)

    # Step 1: Render depth maps via 3DGS
    print("\n" + "=" * 60)
    print("  Step 1: Rendering depth maps via 3DGS")
    print("=" * 60)
    from real_3dgs import Real3DGS
    depth_dir = Path("demo_depth_frames")

    for scene_name, ply_path, _ in scenes:
        scene_depth_dir = depth_dir / scene_name
        scene_depth_dir.mkdir(parents=True, exist_ok=True)
        # Clear old
        for f in scene_depth_dir.glob("*.png"):
            f.unlink()

        print(f"\n  {scene_name}: loading {ply_path}...")
        renderer = Real3DGS(ply_path)
        poses = make_camera_path(scene_name, frames=24)

        # Render each frame
        for i, pose in enumerate(poses):
            out = renderer.render_depth_map(scene_name, pose, i)
            # Move from real_depth_maps/ to demo_depth_frames/<scene>/
            src = Path(out)
            dst = scene_depth_dir / f"frame_{i:04d}.png"
            if src.exists() and src != dst:
                import shutil
                shutil.move(str(src), str(dst))
            if i % 6 == 0:
                print(f"    Frame {i:02d} rendered")

        print(f"  {scene_name}: {len(poses)} depth frames → {scene_depth_dir}")
        del renderer; torch.cuda.empty_cache()

    # Step 2: ControlNet + AnimateDiff
    print("\n" + "=" * 60)
    print("  Step 2: ControlNet + AnimateDiff RGB generation")
    print("=" * 60)
    from controlnet_renderer import ControlNetRenderer

    for scene_name, _, prompt in scenes:
        scene_depth_dir = depth_dir / scene_name
        frames = sorted(scene_depth_dir.glob("frame_*.png"))
        if not frames:
            print(f"  {scene_name}: NO depth frames, skipping")
            continue

        cn = ControlNetRenderer()
        rgb_dir = Path("controlnet_output") / f"{scene_name}_rgb"
        rgb_dir.mkdir(parents=True, exist_ok=True)
        for f in rgb_dir.glob("*.png"):
            f.unlink()

        print(f"\n  {scene_name}: {len(frames)} depth → RGB (AnimateDiff)...")
        frame_paths = [str(p) for p in frames]
        try:
            cn.render_animated(frame_paths, prompt, str(rgb_dir),
                              num_inference_steps=25, seed=42,
                              controlnet_conditioning_scale=1.7,
                              normalize_depth=True)
        except Exception as e:
            print(f"  AnimateDiff failed: {e}, fallback per-frame")
            cn.render_batch(str(scene_depth_dir), prompt, str(rgb_dir),
                           num_inference_steps=25, seed=42,
                           controlnet_conditioning_scale=1.7,
                           normalize_depth=True)

        # Step 3: RAFT + video
        print(f"\n  Step 3: RAFT interpolation + video...")
        from frame_interpolator import FrameInterpolator
        interp = FrameInterpolator()
        rgb_frames = sorted([str(p) for p in rgb_dir.glob("*.png")])
        interp_dir = Path("controlnet_output") / f"{scene_name}_interp"
        interp_dir.mkdir(parents=True, exist_ok=True)
        rgb_frames = interp.interpolate_sequence(rgb_frames, multiplier=3, output_dir=str(interp_dir))

        from video_renderer import VideoRenderer
        vr = VideoRenderer()
        out_path = f"static/videos/{scene_name}_demo.mp4"
        vr.stitch(rgb_frames, out_path, fps=24)
        print(f"  Output: {out_path} ({len(rgb_frames)} frames)")

        del cn, interp; torch.cuda.empty_cache()
        import gc; gc.collect()

    print("\n" + "=" * 60)
    print("  Pipeline complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
