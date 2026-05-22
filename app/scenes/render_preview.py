"""
CineAnchor Blender 预览渲染

直接渲染 GLB 场景 (RGB) + 相机运镜 → PNG 帧序列

用法: blender --background --python render_preview.py -- input.json
"""

import sys
import os
import json
import math
import bpy


def setup_preview_world():
    """预览光照 — 天空色背景 + 环境光"""
    world = bpy.context.scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.5, 0.6, 0.75, 1.0)
    bg.inputs["Strength"].default_value = 1.0

def setup_preview_lights():
    """检查 GLB 自带灯光, 如果没有则补一个"""
    light_count = sum(1 for o in bpy.context.scene.objects if o.type == 'LIGHT')
    if light_count > 0:
        print(f"[PreviewRender] 使用 GLB 自带 {light_count} 个灯光")
        return
    print("[PreviewRender] GLB 无灯光, 添加默认光照")
    bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
    sun = bpy.context.active_object
    sun.data.energy = 3.0


# ── 参数 ──────────────────────────────────────────────────
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not args:
    print("ERROR: 需要 JSON 输入文件路径")
    sys.exit(1)

with open(args[0]) as f:
    inp = json.load(f)

glb_path = inp["glb_path"]
output_dir = inp["output_dir"]
frames = inp["frames"]
res_x = inp.get("resolution_x", 768)
res_y = inp.get("resolution_y", 512)
engine = inp.get("engine", "BLENDER_EEVEE")
samples = inp.get("samples", 16)

os.makedirs(output_dir, exist_ok=True)

# ── 清理 ──────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for m in bpy.data.materials:
    bpy.data.materials.remove(m)

# ── 导入 GLB ──────────────────────────────────────────────
bpy.ops.import_scene.gltf(filepath=glb_path)
mesh_count = sum(1 for o in bpy.context.scene.objects if o.type == 'MESH')
print(f"[PreviewRender] GLB: {glb_path} ({mesh_count} meshes)")

setup_preview_world()
setup_preview_lights()

# ── 渲染引擎设置 ──────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine = engine
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.view_settings.view_transform = 'Standard'

if engine == 'CYCLES':
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    # 使用 GPU 渲染
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'CUDA'
    prefs.get_devices()
    for dev in prefs.devices:
        dev.use = dev.type == 'CUDA'
    scene.cycles.device = 'GPU'
else:
    scene.eevee.taa_render_samples = samples

# ── 逐帧渲染 ──────────────────────────────────────────────
for fi, frame in enumerate(frames):
    pos = frame["position"]
    target = frame["target"]
    fov = frame.get("fov", 55)

    for obj in list(bpy.data.objects):
        if obj.type == 'CAMERA' and obj.name.startswith('PreviewCam'):
            bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.object.camera_add(location=pos)
    cam = bpy.context.active_object
    cam.name = f"PreviewCam_{fi}"
    cam.data.lens_unit = 'FOV'
    cam.data.angle = math.radians(fov)

    dx, dy, dz = target[0] - pos[0], target[1] - pos[1], target[2] - pos[2]
    rot_z = math.atan2(dy, dx)
    dist_xy = math.sqrt(dx*dx + dy*dy)
    rot_x = -math.atan2(dz, dist_xy) if dist_xy > 0.001 else -math.pi / 2
    cam.rotation_euler = (rot_x, 0, rot_z)
    scene.camera = cam

    frame_path = os.path.join(output_dir, f"preview_{fi:05d}.png")
    scene.render.filepath = frame_path
    bpy.ops.render.render(write_still=True)

    print(f"[PreviewRender] {fi+1}/{len(frames)}: {frame_path}")

print(f"[PreviewRender] 完成: {len(frames)} frames → {output_dir}")
