"""
CineAnchor Blender 场景辅助库 v2

新增:
- PBR 图像纹理材质 (ambientCG 贴图集)
- HDRI 环境光照
- 法线贴图 + 置换
"""

import bpy
import math
import random
import os

# 纹理根目录
TEXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "textures")


def _find_map(texture_set, map_suffix):
    """在纹理集中查找指定贴图文件"""
    set_dir = os.path.join(TEXTURES_DIR, texture_set)
    if not os.path.isdir(set_dir):
        return None
    for f in os.listdir(set_dir):
        if map_suffix.lower() in f.lower() and f.endswith('.jpg'):
            return os.path.join(set_dir, f)
    return None


# ═══════════════════════════════════════════════════════════
# PBR 材质 (使用真实图像纹理)
# ═══════════════════════════════════════════════════════════

def material_pbr(name, texture_set, roughness_override=None, metallic_override=None,
                 scale=(1, 1, 1), bump_strength=0.03, displacement_scale=0.02):
    """
    从 ambientCG 纹理集创建 PBR 材质。
    自动查找 Color/Roughness/Normal/Displacement 贴图。
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # 纹理坐标 (可缩放)
    texcoord = nodes.new('ShaderNodeTexCoord')
    texcoord.location = (-1000, 400)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-800, 400)
    mapping.inputs['Scale'].default_value = scale
    links.new(texcoord.outputs['UV'], mapping.inputs['Vector'])

    # === Color ===
    color_path = _find_map(texture_set, 'Color')
    color_tex = nodes.new('ShaderNodeTexImage')
    color_tex.location = (-600, 200)
    color_tex.label = "Color"
    if color_path:
        color_tex.image = bpy.data.images.load(color_path)
    links.new(mapping.outputs['Vector'], color_tex.inputs['Vector'])

    # === Roughness ===
    rough_path = _find_map(texture_set, 'Roughness')
    rough_tex = nodes.new('ShaderNodeTexImage')
    rough_tex.location = (-600, -50)
    rough_tex.label = "Roughness"
    if rough_path:
        rough_tex.image = bpy.data.images.load(rough_path)
        rough_tex.image.colorspace_settings.name = 'Non-Color'
    links.new(mapping.outputs['Vector'], rough_tex.inputs['Vector'])

    # === Metallic ===
    metal_path = _find_map(texture_set, 'Metalness')
    metal_tex = nodes.new('ShaderNodeTexImage')
    metal_tex.location = (-600, -300)
    metal_tex.label = "Metallic"
    if metal_path:
        metal_tex.image = bpy.data.images.load(metal_path)
        metal_tex.image.colorspace_settings.name = 'Non-Color'
    links.new(mapping.outputs['Vector'], metal_tex.inputs['Vector'])

    # === Normal ===
    normal_path = _find_map(texture_set, 'NormalGL')
    normal_tex = nodes.new('ShaderNodeTexImage')
    normal_tex.location = (-600, -550)
    normal_tex.label = "Normal"
    if normal_path:
        normal_tex.image = bpy.data.images.load(normal_path)
        normal_tex.image.colorspace_settings.name = 'Non-Color'
    links.new(mapping.outputs['Vector'], normal_tex.inputs['Vector'])

    normal_map = nodes.new('ShaderNodeNormalMap')
    normal_map.location = (-400, -550)
    normal_map.inputs['Strength'].default_value = bump_strength * 30
    links.new(normal_tex.outputs['Color'], normal_map.inputs['Color'])

    # === Displacement ===
    disp_path = _find_map(texture_set, 'Displacement')
    disp_tex = nodes.new('ShaderNodeTexImage')
    disp_tex.location = (-600, -800)
    disp_tex.label = "Displacement"
    if disp_path:
        disp_tex.image = bpy.data.images.load(disp_path)
        disp_tex.image.colorspace_settings.name = 'Non-Color'
    links.new(mapping.outputs['Vector'], disp_tex.inputs['Vector'])

    # === Principled BSDF ===
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 200)
    links.new(color_tex.outputs['Color'], bsdf.inputs['Base Color'])

    if rough_path:
        links.new(rough_tex.outputs['Color'], bsdf.inputs['Roughness'])
    elif roughness_override is not None:
        bsdf.inputs['Roughness'].default_value = roughness_override

    if metal_path:
        links.new(metal_tex.outputs['Color'], bsdf.inputs['Metallic'])
    elif metallic_override is not None:
        bsdf.inputs['Metallic'].default_value = metallic_override

    links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])

    # === Displacement 输出 ===
    if disp_path:
        disp_node = nodes.new('ShaderNodeDisplacement')
        disp_node.location = (200, -800)
        disp_node.inputs['Scale'].default_value = displacement_scale
        links.new(disp_tex.outputs['Color'], disp_node.inputs['Height'])
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (600, 200)
        links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])

    # === Output ===
    output = nodes.get('ShaderNodeOutputMaterial')
    if not output:
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (600, 200)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    return mat


def material_simple(name, color, roughness=0.5, metallic=0.0):
    """简单单色 PBR 材质 (不需要纹理时使用)"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def material_emissive(name, color, strength=10.0):
    """自发光材质"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 0)
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.1
    bsdf.inputs['Emission Color'].default_value = (*color, 1.0)
    bsdf.inputs['Emission Strength'].default_value = strength

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (500, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    return mat


def material_procedural(name, color_a, color_b, roughness=0.3, metallic=0.8,
                        scale=3.0, bump_strength=0.02):
    """程序化双色材质 — 噪声混合两个颜色 + 凹凸"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    texcoord = nodes.new('ShaderNodeTexCoord')
    texcoord.location = (-800, 200)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-600, 200)
    mapping.inputs['Scale'].default_value = (scale, scale, scale)
    links.new(texcoord.outputs['Object'], mapping.inputs['Vector'])

    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-400, 200)
    noise.inputs['Scale'].default_value = 4.0
    noise.inputs['Detail'].default_value = 2.0
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

    mix = nodes.new('ShaderNodeMix')
    mix.location = (-200, 200)
    mix.data_type = 'RGBA'
    mix.inputs['Factor'].default_value = 0.5
    mix.inputs['A'].default_value = (*color_a, 1.0)
    mix.inputs['B'].default_value = (*color_b, 1.0)
    links.new(noise.outputs['Fac'], mix.inputs['Factor'])

    bump_node = nodes.new('ShaderNodeBump')
    bump_node.location = (0, -100)
    bump_node.inputs['Strength'].default_value = bump_strength
    links.new(noise.outputs['Fac'], bump_node.inputs['Height'])

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 200)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    links.new(bump_node.outputs['Normal'], bsdf.inputs['Normal'])

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (500, 200)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    return mat


# ═══════════════════════════════════════════════════════════
# 光照
# ═══════════════════════════════════════════════════════════

def setup_world(sky_color=(0.1, 0.15, 0.3), strength=1.0):
    bpy.context.scene.world.use_nodes = True
    bg = bpy.context.scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*sky_color, 1.0)
    bg.inputs["Strength"].default_value = strength


def add_volume_mist(density=0.03, anisotropy=0.3, color=(0.85, 0.82, 0.75)):
    """体积雾"""
    bpy.context.scene.world.use_nodes = True
    nodes = bpy.context.scene.world.node_tree.nodes
    links = bpy.context.scene.world.node_tree.links

    vol_scatter = nodes.new("ShaderNodeVolumeScatter")
    vol_scatter.location = (-200, -150)
    vol_scatter.inputs["Density"].default_value = density
    vol_scatter.inputs["Anisotropy"].default_value = anisotropy
    vol_scatter.inputs["Color"].default_value = (*color, 1.0)

    world_output = nodes.get("World Output")
    if not world_output:
        world_output = nodes.new("ShaderNodeOutputWorld")
    links.new(vol_scatter.outputs["Volume"], world_output.inputs["Volume"])


# ═══════════════════════════════════════════════════════════
# 几何辅助
# ═══════════════════════════════════════════════════════════

def add_modifiers(obj, subsurf=0, bevel=True, bevel_width=0.02):
    if subsurf > 0:
        mod = obj.modifiers.new("Subdiv", 'SUBSURF')
        mod.levels = subsurf
        mod.render_levels = subsurf
    if bevel:
        mod = obj.modifiers.new("Bevel", 'BEVEL')
        mod.width = bevel_width
        mod.segments = 2


def randomize_vertices(obj, strength=0.05):
    for vert in obj.data.vertices:
        vert.co.x += random.uniform(-strength, strength)
        vert.co.y += random.uniform(-strength, strength)
        vert.co.z += random.uniform(-strength, strength)


def setup_camera(location=(7, -6, 4), look_at=(0, 0, 0.5), fov=55):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.active_object
    cam.name = "CineAnchorCamera"
    cam.data.lens_unit = 'FOV'
    cam.data.angle = math.radians(fov)

    direction = (
        look_at[0] - location[0],
        look_at[1] - location[1],
        look_at[2] - location[2],
    )
    rot_z = math.atan2(direction[1], direction[0])
    dist_xy = math.sqrt(direction[0]**2 + direction[1]**2)
    rot_x = -math.atan2(direction[2], dist_xy)
    cam.rotation_euler = (rot_x, 0, rot_z)

    bpy.context.scene.camera = cam
    return cam


# ═══════════════════════════════════════════════════════════
# 场景设置
# ═══════════════════════════════════════════════════════════

def setup_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)


def export_glb(filepath):
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        export_apply=True,
        export_image_format='JPEG',
    )
    print(f"[CineAnchor] 场景已导出: {filepath}")
