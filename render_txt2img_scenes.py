"""
Generate scene videos with txt2img (no depth) + seed walking + RAFT interpolation.
Bypasses the ControlNet depth mismatch issue by using SD's native text-to-image capability.
"""
import torch
import os
import sys
import numpy as np
from pathlib import Path
from PIL import Image
from diffusers import StableDiffusionPipeline

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

device = torch.device("cuda")

print("Loading SD 1.5...")
pipe = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float16,
    safety_checker=None,
).to(device)
pipe.enable_model_cpu_offload()
pipe.enable_vae_slicing()

scenes = [
    ("zen_garden",       "a serene japanese zen garden with cherry blossoms, wooden bridge over pond, stone path, pine trees, golden hour lighting, photorealistic, high quality, sharp focus, masterpiece"),
    ("scifi_corridor",   "a futuristic sci-fi corridor with neon blue lights, metallic walls, glass panels, cyberpunk aesthetic, cinematic lighting, photorealistic, sharp focus, masterpiece"),
    ("floating_islands", "floating islands in a fantasy sky, waterfalls cascading off edges, crystal formations, clouds, epic fantasy art, photorealistic, sharp focus, masterpiece"),
    ("desert_ruins",     "ancient egyptian desert ruins, a stone pyramid at center, stone columns and obelisks, sand dunes, harsh sunlight, photorealistic, sharp focus, masterpiece"),
    ("forest_glade",     "a sunny forest glade with giant ancient trees, moss covered ground, stone circle, god rays through canopy, photorealistic, sharp focus, masterpiece"),
]

neg_prompt = "blurry, low quality, distorted, abstract, ugly, deformed, watermark, text, bad anatomy"

out_base = Path("controlnet_output")
videos_dir = Path("static/videos")
videos_dir.mkdir(parents=True, exist_ok=True)

for scene_name, prompt in scenes:
    print(f"\n{'='*60}")
    print(f"  {scene_name}")
    print(f"{'='*60}")

    rgb_dir = out_base / f"{scene_name}_rgb"
    rgb_dir.mkdir(parents=True, exist_ok=True)
    for f in rgb_dir.glob("*.png"):
        f.unlink()

    base_seed = 42
    seed_step = 2  # small seed change = slight variation between frames

    print(f"  Generating 24 frames (seed walking, step={seed_step})...")
    for i in range(24):
        seed = base_seed + i * seed_step
        generator = torch.Generator(device).manual_seed(seed)

        with torch.inference_mode():
            out = pipe(
                prompt=prompt,
                negative_prompt=neg_prompt,
                num_inference_steps=30,
                guidance_scale=8.0,
                generator=generator,
                width=576,
                height=576,
            )

        path = rgb_dir / f"rgb_frame_{i:04d}.png"
        # Light polish
        from PIL import ImageEnhance, ImageFilter
        img = out.images[0]
        img = ImageEnhance.Contrast(img).enhance(1.05)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=3))
        img.save(str(path))

        if i % 6 == 0:
            print(f"    Frame {i:02d} done (seed={seed})")

    # RAFT 3x interpolation
    from frame_interpolator import FrameInterpolator
    interp = FrameInterpolator()
    rgb_frames = sorted([str(p) for p in rgb_dir.glob("*.png")])
    interp_dir = out_base / f"{scene_name}_interp"
    interp_dir.mkdir(parents=True, exist_ok=True)
    rgb_frames = interp.interpolate_sequence(rgb_frames, multiplier=3, output_dir=str(interp_dir))
    print(f"  RAFT: {len(rgb_frames)} frames")

    # ffmpeg → MP4
    from video_renderer import VideoRenderer
    vr = VideoRenderer()
    out_path = str(videos_dir / f"{scene_name}_demo.mp4")
    vr.stitch(rgb_frames, out_path, fps=24)
    print(f"  Output: {out_path}")

    torch.cuda.empty_cache()

print("\nDone!")
