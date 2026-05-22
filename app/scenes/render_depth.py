"""
CineAnchor 深度图渲染 v5

三种渲染策略 (按稳健性排序):
  1. EEVEE + AOV (最快, 质量可接受)
  2. Cycles + emission shader (高质量)
  3. Cycles + Mist Pass (最稳健)

输出: 8-bit 归一化深度 PNG (0=远, 255=近)

用法: blender --background --python render_depth.py -- input.json
"""

import sys
import os
import json
import math
import bpy


def create_depth_material(far_clip=25.0, near_clip=0.5):
    """
    Depth shader with full-range normalization.

    Node graph:
      Camera Data → View Distance
        → Map Range [near_clip, far_clip] → [1.0, 0.0]  (near=bright)
        → Emission Strength
    """
    mat = bpy.data.materials.new("DepthMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    cam_data = nodes.new('ShaderNodeCameraData')
    cam_data.location = (-600, 0)

    map_range = nodes.new('ShaderNodeMapRange')
    map_range.location = (-300, 0)
    map_range.inputs['From Min'].default_value = near_clip
    map_range.inputs['From Max'].default_value = far_clip
    map_range.inputs['To Min'].default_value = 1.0
    map_range.inputs['To Max'].default_value = 0.0

    emission = nodes.new('ShaderNodeEmission')
    emission.location = (0, 0)
    emission.inputs['Color'].default_value = (1, 1, 1, 1)

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (200, 0)

    links.new(cam_data.outputs['View Distance'], map_range.inputs['Value'])
    links.new(map_range.outputs['Result'], emission.inputs['Strength'])
    links.new(emission.outputs['Emission'], output.inputs['Surface'])

    return mat


def override_materials(depth_mat):
    """覆写所有 MESH 物体的材质为深度材质"""
    count = 0
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.data.materials.clear()
            obj.data.materials.append(depth_mat)
            count += 1
    return count


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
far_clip = inp.get("far_clip", 25.0)
engine = inp.get("engine", "CYCLES")  # 可选 "BLENDER_EEVEE"
samples = inp.get("samples", 32)

os.makedirs(output_dir, exist_ok=True)

# ── 清理 ──────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for m in bpy.data.materials:
    bpy.data.materials.remove(m)

# ── 导入 GLB ──────────────────────────────────────────────
bpy.ops.import_scene.gltf(filepath=glb_path)
mesh_count = sum(1 for o in bpy.context.scene.objects if o.type == 'MESH')
print(f"[DepthRender] GLB: {glb_path} ({mesh_count} meshes)")

# ── 深度材质覆写 ──────────────────────────────────────────
depth_mat = create_depth_material(far_clip)
overridden = override_materials(depth_mat)
print(f"[DepthRender] 材质覆写: {overridden} objects")

# ── 渲染引擎设置 ──────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine = engine
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'

# 使用 Standard 色彩管理 — 比 Filmic 保留更多暗部细节
# Filmic 会压暗深度图, 改成 Standard 让深度数据更可读
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'

if engine == 'CYCLES':
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    print(f"[DepthRender] Cycles {samples} samples")
else:
    scene.eevee.taa_render_samples = samples
    print(f"[DepthRender] EEVEE {samples} TAA samples")

# ── Compositor: pass-through (no post-processing) ─────────
# Depth normalization is done in the shader via Map Range node
scene.use_nodes = False

# ── 逐帧渲染 ──────────────────────────────────────────────
for fi, frame in enumerate(frames):
    pos = frame["position"]
    target = frame["target"]
    fov = frame.get("fov", 55)

    # 移除旧相机
    for obj in list(bpy.data.objects):
        if obj.type == 'CAMERA' and obj.name.startswith('DepthCam'):
            bpy.data.objects.remove(obj, do_unlink=True)

    # 新相机
    bpy.ops.object.camera_add(location=pos)
    cam = bpy.context.active_object
    cam.name = f"DepthCam_{fi}"
    cam.data.lens_unit = 'FOV'
    cam.data.angle = math.radians(fov)
    cam.data.clip_start = 0.1
    cam.data.clip_end = far_clip * 2

    # 瞄准: 计算从位置到目标的方向
    dx, dy, dz = target[0] - pos[0], target[1] - pos[1], target[2] - pos[2]
    rot_z = math.atan2(dy, dx)
    dist_xy = math.sqrt(dx*dx + dy*dy)
    rot_x = -math.atan2(dz, dist_xy) if dist_xy > 0.001 else -math.pi / 2
    cam.rotation_euler = (rot_x, 0, rot_z)
    scene.camera = cam

    frame_path = os.path.join(output_dir, f"frame_{fi:05d}.png")
    scene.render.filepath = frame_path
    bpy.ops.render.render(write_still=True)

    print(f"[DepthRender] {fi+1}/{len(frames)}: {frame_path}")

print(f"[DepthRender] 完成: {len(frames)} → {output_dir}")
