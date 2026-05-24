"""
Full pipeline v3: Blender depth render + 16→8bit conversion + ControlNet + video.
Uses mac's fixed render_depth.py v6 and the camera paths from SQLite.
"""
import os, sys, json, tempfile, subprocess, math
from pathlib import Path
import numpy as np
from PIL import Image

os.chdir(Path(__file__).parent)

BLENDER = r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe'
DEPTH_SCRIPT = 'app/scenes/render_depth.py'
DB_PATH = 'data/cineanchor.db'
DEMO_DIR = Path('demo_depth_frames')
OUT_DIR = Path('controlnet_output')
VIDEO_DIR = Path('static/videos')
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

SCENE_MAP = {
    'zen_garden':       ('scene_07d1309acadd', 'path_12cf8b0b0892',
                         'a serene japanese zen garden with cherry blossoms, wooden bridge over pond, stone path, pine trees, golden hour lighting, photorealistic, masterpiece'),
    'scifi_corridor':   ('scene_b1a44b678ef6', 'path_d55a6009ef52',
                         'a futuristic sci-fi corridor with neon blue lights, metallic walls, pillars, cyberpunk aesthetic, cinematic lighting, photorealistic, masterpiece'),
    'floating_islands': ('scene_a295ed3dfd26', 'path_efd95eebb42f',
                         'floating islands in a fantasy sky, waterfalls cascading off edges, crystal formations, clouds, epic fantasy art, photorealistic, masterpiece'),
    'desert_ruins':     ('scene_ec9c416cc431', 'path_457323c27fba',
                         'ancient egyptian desert ruins, a stone pyramid at center, stone columns and obelisks, sand dunes, harsh sunlight, cinematic, photorealistic, masterpiece'),
    'forest_glade':     ('scene_05f0a34a352a', 'path_9ae9b98b54cb',
                         'a sunny forest glade with giant ancient trees, moss covered ground, stone circle, god rays through canopy, nature, photorealistic, masterpiece'),
}


def render_depth_frames(scene_name, scene_id, path_id):
    """Step 1: Render 16-bit depth frames with Blender v6."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    model_row = conn.execute('SELECT model_path FROM scenes WHERE id=?', (scene_id,)).fetchone()
    kf_row = conn.execute('SELECT keyframes, fps FROM camera_paths WHERE id=?', (path_id,)).fetchone()
    conn.close()

    glb_path = model_row[0]
    keyframes = json.loads(kf_row[0])
    fps = kf_row[1]

    # Generate frames with Catmull-Rom interpolation (from depth_renderer.py)
    from app.depth_renderer import _interpolate_keyframes, _three_to_blender_pose
    frames_3js = _interpolate_keyframes(keyframes, fps)

    # Pick 24 evenly-spaced frames
    if len(frames_3js) > 24:
        step = len(frames_3js) / 24
        frames_3js = [frames_3js[int(i * step)] for i in range(24)]

    # Convert to Blender coords
    blender_frames = []
    for f in frames_3js:
        target3 = f.get('target')
        if target3 is None:
            from app.depth_renderer import _target_from_quat
            target3 = _target_from_quat(f['pos'], f['quat'])
        pos, target = _three_to_blender_pose(f['pos'], target3)
        blender_frames.append({
            'position': list(pos),
            'target': list(target),
            'fov': f.get('fov', 55),
        })

    out_dir = DEMO_DIR / scene_name
    out_dir.mkdir(parents=True, exist_ok=True)

    render_input = {
        'glb_path': glb_path,
        'output_dir': str(out_dir.absolute()),
        'frames': blender_frames,
        'resolution_x': 768,
        'resolution_y': 512,  # Blender v6 expects 768x512
        'near_clip': 0,  # auto
        'far_clip': 0,   # auto
        'engine': 'CYCLES',
        'samples': 8,    # fast
    }

    inp_path = Path(tempfile.gettempdir()) / f'cineanchor_depth_{scene_name}.json'
    inp_path.write_text(json.dumps(render_input, ensure_ascii=False), encoding='utf-8')

    env = os.environ.copy()
    env['CINEANCHOR_ROOT'] = str(Path.cwd())

    print(f'  Blender rendering {len(blender_frames)} frames...')
    result = subprocess.run(
        [BLENDER, '--background', '--python', DEPTH_SCRIPT, '--', str(inp_path)],
        capture_output=True, text=True, timeout=600,
        env=env, encoding='utf-8', errors='replace',
    )

    # Check for errors
    if result.returncode != 0:
        print(f'  Blender error: {result.stderr[-500:]}')
        return False

    # Print quality lines
    for line in result.stdout.splitlines():
        if '[DepthRender v6]' in line and ('OK' in line or 'LOW' in line or '质量' in line or 'frames' in line):
            print(f'  {line.strip()}')

    # Clean up
    inp_path.unlink()
    return True


def convert_16bit_to_8bit(scene_name):
    """Step 2: Convert 16-bit depth frames to 8-bit with global normalization."""
    scene_dir = DEMO_DIR / scene_name
    frames = sorted(scene_dir.glob('frame_*.png'))
    if not frames:
        print(f'  No frames found in {scene_dir}')
        return False

    # Read all frames as 16-bit
    all_data = []
    for f in frames:
        img = Image.open(str(f))
        arr = np.array(img, dtype=np.float64)
        if arr.ndim == 3:
            arr = arr[:, :, 0].astype(np.float64)  # take first channel
        all_data.append(arr)

    # Global 2-98 percentile normalization
    all_vals = np.concatenate([a.ravel() for a in all_data])
    v_min, v_max = np.percentile(all_vals, 2), np.percentile(all_vals, 98)
    if v_max - v_min < 0.1:
        v_min, v_max = all_vals.min(), all_vals.max()
    if v_max - v_min < 0.1:
        v_min, v_max = 0, 65535

    good = 0
    for f, data in zip(frames, all_data):
        norm = np.clip((data - v_min) / (v_max - v_min) * 255, 0, 255).astype(np.uint8)
        Image.fromarray(norm).save(str(f))
        if len(np.unique(norm)) > 50:
            good += 1

    print(f'  Converted {len(frames)} frames to 8-bit (range [{v_min:.0f}, {v_max:.0f}])')
    print(f'  {good}/{len(frames)} frames above quality threshold (>50 unique)')
    return good > 0


def run_controlnet_pipeline(scene_name, prompt):
    """Step 3-5: ControlNet → RAFT → MP4."""
    from controlnet_renderer import ControlNetRenderer
    from frame_interpolator import FrameInterpolator
    from video_renderer import VideoRenderer

    scene_dir = DEMO_DIR / scene_name
    frames = sorted(scene_dir.glob('frame_*.png'))
    if not frames:
        return False

    cn = ControlNetRenderer()
    rgb_dir = OUT_DIR / f'{scene_name}_rgb'
    rgb_dir.mkdir(parents=True, exist_ok=True)
    for f in rgb_dir.glob('*.png'):
        f.unlink()

    frame_paths = [str(p) for p in frames]
    try:
        cn.render_animated(frame_paths, prompt, str(rgb_dir),
                          num_inference_steps=25, seed=42,
                          controlnet_conditioning_scale=1.7,
                          normalize_depth=True)
    except Exception as e:
        print(f'  AnimateDiff failed: {e}, fallback per-frame')
        cn.render_batch(str(scene_dir), prompt, str(rgb_dir),
                       num_inference_steps=25, seed=42,
                       controlnet_conditioning_scale=1.7,
                       normalize_depth=True)

    # RAFT
    interp = FrameInterpolator()
    rgb_frames = sorted([str(p) for p in rgb_dir.glob('*.png')])
    interp_dir = OUT_DIR / f'{scene_name}_interp'
    interp_dir.mkdir(parents=True, exist_ok=True)
    rgb_frames = interp.interpolate_sequence(rgb_frames, multiplier=3, output_dir=str(interp_dir))

    # Video
    vr = VideoRenderer()
    out_path = str(VIDEO_DIR / f'{scene_name}_demo.mp4')
    vr.stitch(rgb_frames, out_path, fps=24)
    print(f'  Video: {out_path} ({len(rgb_frames)} frames)')

    del cn, interp
    import torch; torch.cuda.empty_cache()
    import gc; gc.collect()
    return True


# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=str, default=None)
    parser.add_argument('--skip-render', action='store_true', help='Skip Blender (use existing frames)')
    parser.add_argument('--skip-controlnet', action='store_true', help='Skip ControlNet (only render depth)')
    args = parser.parse_args()

    scenes = list(SCENE_MAP.items())
    if args.scene:
        scenes = [(s, v) for s, v in scenes if s == args.scene]

    for scene_name, (scene_id, path_id, prompt) in scenes:
        print(f'\n{"="*60}')
        print(f'  {scene_name.upper()}')
        print(f'{"="*60}')

        if not args.skip_render:
            print('[1/3] Rendering depth frames...')
            if not render_depth_frames(scene_name, scene_id, path_id):
                continue

            print('[2/3] Converting 16-bit → 8-bit...')
            if not convert_16bit_to_8bit(scene_name):
                continue
        else:
            print('[1/3] Skipping render (--skip-render)')
            print('[2/3] Skipping convert (--skip-render)')

        if not args.skip_controlnet:
            print('[3/3] ControlNet + AnimateDiff + RAFT + MP4...')
            run_controlnet_pipeline(scene_name, prompt)
        else:
            print('[3/3] Skipping ControlNet (--skip-controlnet)')

    print('\nDone!')
