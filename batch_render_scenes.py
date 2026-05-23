"""Batch render 5 scenes from demo_depth_frames → MP4 videos.
Usage:
    python batch_render_scenes.py              # AnimateDiff mode (default, temporal smooth)
    python batch_render_scenes.py --per-frame   # Per-frame mode (sharper, then RAFT interpolate)
    python batch_render_scenes.py --no-normalize # Disable depth normalization
"""
import os, sys, argparse
from pathlib import Path

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

parser = argparse.ArgumentParser()
parser.add_argument("--per-frame", action="store_true",
                    help="Use per-frame ControlNet (sharper) + RAFT instead of AnimateDiff")
parser.add_argument("--no-normalize", action="store_true",
                    help="Disable depth map normalization")
parser.add_argument("--scene", type=str, default=None,
                    help="Render only a specific scene name")
args = parser.parse_args()

scenes = [
    ("zen_garden",       "a serene japanese zen garden, cherry blossoms, golden hour lighting, photorealistic, 8K"),
    ("scifi_corridor",   "a futuristic scifi corridor, neon lights, cyberpunk, metallic walls, cinematic, 8K"),
    ("floating_islands", "floating islands in the sky, waterfalls, crystals, fantasy, epic cinematography, 8K"),
    ("desert_ruins",     "ancient desert ruins, pyramids, sand dunes, harsh sunlight, cinematic, 8K"),
    ("forest_glade",     "a sunny forest glade, god rays through trees, moss, nature, photorealistic, 8K"),
]

if args.scene:
    scenes = [(s, p) for s, p in scenes if s == args.scene]
    if not scenes:
        print(f"Scene '{args.scene}' not found. Choose from: zen_garden, scifi_corridor, floating_islands, desert_ruins, forest_glade")
        sys.exit(1)

normalize = not args.no_normalize
print(f"Mode: {'Per-frame (sharper)' if args.per_frame else 'AnimateDiff (temporal smooth)'}, "
      f"Depth normalization: {normalize}")

base = Path("demo_depth_frames")
videos_dir = Path("static/videos")
videos_dir.mkdir(parents=True, exist_ok=True)

for scene_name, prompt in scenes:
    scene_dir = base / scene_name
    if not scene_dir.exists():
        print(f"SKIP {scene_name}: directory not found")
        continue

    frames = sorted(scene_dir.glob("frame_*.png"))
    print(f"\n{'='*60}")
    print(f"  {scene_name}: {len(frames)} depth frames")
    print(f"  Prompt: {prompt}")
    print(f"{'='*60}")

    from controlnet_renderer import ControlNetRenderer
    cn = ControlNetRenderer()

    rgb_dir = Path("controlnet_output") / f"{scene_name}_rgb"
    rgb_dir.mkdir(parents=True, exist_ok=True)
    # Clear old frames
    for f in rgb_dir.glob("*.png"):
        f.unlink()

    if args.per_frame:
        # Per-frame mode: sharper individual frames + RAFT interpolation
        cn.render_batch(
            str(scene_dir), prompt, str(rgb_dir),
            num_inference_steps=25, seed=42,
            controlnet_conditioning_scale=1.7,
            normalize_depth=normalize,
        )
    else:
        # AnimateDiff mode: temporal consistency
        try:
            frame_paths = [str(p) for p in frames]
            cn.render_animated(
                frame_paths, prompt, str(rgb_dir),
                num_inference_steps=25, seed=42,
                controlnet_conditioning_scale=1.7,
                normalize_depth=normalize,
            )
            print(f"  AnimateDiff: OK")
        except Exception as e:
            print(f"  AnimateDiff failed: {e}")
            # Fallback: per-frame ControlNet
            cn.render_batch(
                str(scene_dir), prompt, str(rgb_dir),
                num_inference_steps=25, seed=42,
                controlnet_conditioning_scale=1.7,
                normalize_depth=normalize,
            )

    # RAFT 3x interpolation
    from frame_interpolator import FrameInterpolator
    interp = FrameInterpolator()
    rgb_frames = sorted([str(p) for p in rgb_dir.glob("*.png")])
    interp_dir = Path("controlnet_output") / f"{scene_name}_interp"
    interp_dir.mkdir(parents=True, exist_ok=True)
    rgb_frames = interp.interpolate_sequence(rgb_frames, multiplier=3, output_dir=str(interp_dir))
    print(f"  RAFT: {len(rgb_frames)} frames after 3x interpolation")

    # ffmpeg → MP4
    from video_renderer import VideoRenderer
    vr = VideoRenderer()
    out_path = str(videos_dir / f"{scene_name}_demo.mp4")
    vr.stitch(rgb_frames, out_path, fps=24)
    print(f"  Output: {out_path}")

    # Cleanup to free VRAM
    del cn, interp
    import gc; gc.collect()
    import torch; torch.cuda.empty_cache()

print("\nDone! All scenes rendered.")
