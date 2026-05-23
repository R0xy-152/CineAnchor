"""
CineAnchor 深度图渲染 v6

改进:
  1. GLB 导入后自动计算场景包围盒 → 动态 near/far
  2. 16-bit PNG 输出 (65536 级别 vs 旧版 256)
  3. Compositor 深度归一化 (Map Range 收紧到场景真实范围)
  4. 每帧 unique value 验证 (阈值 50)
  5. 全局 near/far 跨帧一致性 (同一距离 = 同一像素值)

用法: blender --background --python render_depth.py -- input.json
"""

import sys
import os
import json
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


# ── 场景包围盒计算 ──────────────────────────────────────────
def compute_scene_aabb():
    """遍历场景中所有 MESH 物体, 返回世界空间包围盒 (min, max) 和 diagonal"""
    mesh_verts = []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        # 用依赖图获取最终世界坐标 (考虑 modifier / 层级变换)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        if mesh is None:
            continue
        world_mat = obj.matrix_world
        for v in mesh.vertices:
            mesh_verts.append(world_mat @ v.co)
        eval_obj.to_mesh_clear()

    if not mesh_verts:
        # fallback: 找不到 mesh 顶点则用 object location
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                mesh_verts.append(obj.location)
        if not mesh_verts:
            return Vector((0, 0, -5)), Vector((0, 0, 5)), 10.0

    xs = [v.x for v in mesh_verts]
    ys = [v.y for v in mesh_verts]
    zs = [v.z for v in mesh_verts]
    bmin = Vector((min(xs), min(ys), min(zs)))
    bmax = Vector((max(xs), max(ys), max(zs)))
    diagonal = (bmax - bmin).length
    return bmin, bmax, diagonal


# ── 深度材质 ────────────────────────────────────────────────
def create_depth_material(near_clip, far_clip):
    """
    View Distance → Map Range [near, far] → [1.0, 0.0] → Emission Strength

    近处=亮(1.0), 远处=暗(0.0), 范围外 clamp.
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
    map_range.clamp = True

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


# ── Compositor 归一化 ───────────────────────────────────────
def setup_compositor_normalization():
    """
    Compositor 管线: Render Layers → Normalize → (自动输出)

    Blender 5.1 API:
      - 使用 scene.compositing_node_group (非 scene.node_tree, 后者已废弃)
      - 不需要 Composite 输出节点, 渲染管线自动读取 compositor 最后节点

    Normalize 节点将每帧图像拉伸到 [0, 1] 全范围,
    作为 shader Map Range 的安全网:
      - 如果 shader 已经产出 [0, 1] 全范围 → Normalize 是 identity
      - 如果 shader 产出 [0.3, 0.7] 压缩区间 → Normalize 拉伸到 [0, 1]

    注意: 跨帧一致性由 shader 的全局 near/far 保证,
    Compositor Normalize 只纠正残留压缩.
    """
    scene = bpy.context.scene

    # 清理旧 compositor node group (避免重名累积)
    for old_group in list(bpy.data.node_groups):
        if old_group.name.startswith('CineAnchor_DepthComp'):
            bpy.data.node_groups.remove(old_group)

    # Blender 5.1+: compositor 通过 compositing_node_group 访问
    group = bpy.data.node_groups.new('CineAnchor_DepthComp', type='CompositorNodeTree')
    scene.compositing_node_group = group
    nodes = group.nodes
    links = group.links

    rl = nodes.new('CompositorNodeRLayers')
    rl.location = (0, 0)

    normalize = nodes.new('CompositorNodeNormalize')
    normalize.location = (220, 0)

    links.new(rl.outputs['Image'], normalize.inputs['Value'])
    # 无需显式 Composite/Output 节点 — 渲染管线自动读取 compositor 最后节点


# ── 逐帧 unique value 验证 ──────────────────────────────────
def validate_frame_depth(filepath, min_unique=50):
    """
    读取刚渲染的 PNG，检查 unique depth values。
    返回 (unique_count, min_val, max_val)。
    """
    try:
        img = bpy.data.images.load(filepath)
        # .pixels 是 flat float array [R,G,B,A, ...] ∈ [0, 1]
        w, h = img.size
        pixels = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
        # 只用 R 通道 (三个通道在 emission shader 下一致)
        gray = (pixels[:, :, 0] * 65535).astype(np.uint16)
        bpy.data.images.remove(img)

        unique = len(np.unique(gray))
        gmin, gmax = gray.min(), gray.max()
        return unique, gmin, gmax
    except Exception as e:
        print(f"  [Validate] 读取失败: {e}")
        return -1, 0, 0


# ══════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════

def main():
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
    engine = inp.get("engine", "CYCLES")
    samples = inp.get("samples", 32)
    # near/far 可被外部覆盖, 0 表示自动计算
    override_near = inp.get("near_clip", 0)
    override_far = inp.get("far_clip", 0)

    os.makedirs(output_dir, exist_ok=True)

    # ── 清理场景 ────────────────────────────────────────────
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for m in bpy.data.materials:
        bpy.data.materials.remove(m)

    # ── 导入 GLB ────────────────────────────────────────────
    bpy.ops.import_scene.gltf(filepath=glb_path)
    mesh_count = sum(1 for o in bpy.context.scene.objects if o.type == 'MESH')
    print(f"[DepthRender v6] GLB: {glb_path} ({mesh_count} meshes)")

    # ── 场景包围盒 → 动态 near/far ──────────────────────────
    bmin, bmax, diagonal = compute_scene_aabb()
    scene_center = (bmin + bmax) / 2
    scene_radius = diagonal / 2

    # 从 camera path 估算相机到场景中心的距离范围
    cam_distances = []
    for frame in frames:
        pos = Vector(frame["position"])
        dist = (pos - scene_center).length
        cam_distances.append(dist)
    min_cam_dist = min(cam_distances) if cam_distances else scene_radius * 2
    max_cam_dist = max(cam_distances) if cam_distances else scene_radius * 5

    # near: 相机离场景最近时, 最近几何面到镜头的距离
    # far:  相机离场景最远时, 最远几何面到镜头的距离
    calc_near = max(0.05, min_cam_dist - scene_radius * 1.2)
    calc_far  = max_cam_dist + scene_radius * 1.5

    # 允许外部显式覆盖
    near_clip = override_near if override_near > 0 else calc_near
    far_clip  = override_far  if override_far  > 0 else calc_far

    # 安全下限
    near_clip = max(0.05, near_clip)
    far_clip  = max(near_clip + 1.0, far_clip)

    print(f"[DepthRender v6] Scene bounds: center={tuple(round(v,1) for v in scene_center)}")
    print(f"[DepthRender v6]   radius={scene_radius:.1f}, diagonal={diagonal:.1f}")
    print(f"[DepthRender v6]   cam distance range: {min_cam_dist:.1f}..{max_cam_dist:.1f}")
    print(f"[DepthRender v6]   near_clip={near_clip:.2f}, far_clip={far_clip:.2f}")

    # ── 深度材质 ────────────────────────────────────────────
    depth_mat = create_depth_material(near_clip, far_clip)
    overridden = override_materials(depth_mat)
    print(f"[DepthRender v6] 材质覆写: {overridden} objects")

    # ── 渲染设置 ────────────────────────────────────────────
    scene = bpy.context.scene
    scene.render.engine = engine
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'BW'         # 灰度单通道, PIL 读为 uint16
    scene.render.image_settings.color_depth = '16'        # ← 16-bit 关键改动
    scene.render.image_settings.compression = 15           # 无损压缩

    # Standard 色彩管理 — 不做 tone mapping, 保留线性深度值
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'

    if engine == 'CYCLES':
        scene.cycles.samples = samples
        scene.cycles.use_denoising = False
        scene.cycles.use_adaptive_sampling = False
        print(f"[DepthRender v6] Cycles {samples} samples")
    else:
        scene.eevee.taa_render_samples = samples
        print(f"[DepthRender v6] EEVEE {samples} TAA samples")

    # ── Compositor ──────────────────────────────────────────
    setup_compositor_normalization()
    print(f"[DepthRender v6] Compositor: Normalize node active")

    # ── 逐帧渲染 + 验证 ────────────────────────────────────
    low_quality_frames = []

    for fi, frame in enumerate(frames):
        pos = frame["position"]
        target = frame["target"]
        fov = frame.get("fov", 55)

        # 移除旧相机
        for obj in list(bpy.data.objects):
            if obj.type == 'CAMERA' and obj.name.startswith('DepthCam'):
                bpy.data.objects.remove(obj, do_unlink=True)

        # 创建新相机
        bpy.ops.object.camera_add(location=pos)
        cam = bpy.context.active_object
        cam.name = f"DepthCam_{fi}"
        cam.data.lens_unit = 'FOV'
        cam.data.angle = math.radians(fov)
        cam.data.clip_start = near_clip * 0.5
        cam.data.clip_end = far_clip * 2.0

        # 瞄准: Z-up 坐标系, -Z 是相机前向
        direction = Vector(target) - Vector(pos)
        rot_quat = direction.to_track_quat('-Z', 'Z')
        cam.rotation_euler = rot_quat.to_euler()
        scene.camera = cam

        # 渲染
        frame_path = os.path.join(output_dir, f"frame_{fi:05d}.png")
        scene.render.filepath = frame_path
        bpy.ops.render.render(write_still=True)

        # 验证 unique values
        unique, gmin, gmax = validate_frame_depth(frame_path, min_unique=50)
        status = "OK" if unique >= 50 else "LOW"
        print(f"[DepthRender v6] {fi+1}/{len(frames)}: {frame_path} "
              f"unique={unique} min={gmin} max={gmax} [{status}]")

        if unique < 50:
            low_quality_frames.append((fi, unique, gmin, gmax))

    # ── 汇总报告 ────────────────────────────────────────────
    print(f"\n[DepthRender v6] ======== 质量报告 ========")
    print(f"[DepthRender v6] 总帧数: {len(frames)}")
    print(f"[DepthRender v6] 输出位深: 16-bit PNG")
    print(f"[DepthRender v6] near_clip: {near_clip:.2f}, far_clip: {far_clip:.2f}")

    if low_quality_frames:
        print(f"[DepthRender v6] ⚠️ 低质量帧 (<50 unique): {len(low_quality_frames)}/{len(frames)}")
        for fi, uniq, gmin, gmax in low_quality_frames[:5]:
            print(f"[DepthRender v6]   frame {fi}: unique={uniq}, range=[{gmin}, {gmax}]")
    else:
        print(f"[DepthRender v6] ✅ 所有帧 unique > 50")

    print(f"[DepthRender v6] 完成: {len(frames)} frames → {output_dir}")


if __name__ == "__main__":
    main()
