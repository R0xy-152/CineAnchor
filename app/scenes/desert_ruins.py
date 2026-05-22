"""
CineAnchor 场景: 沙漠遗迹

Blender 无头运行: blender --background --python desert_ruins.py -- params.json
"""

import sys, os, json, math, random
import bpy

sys.path.insert(0, os.environ.get('CINEANCHOR_ROOT',
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.scene_helpers import (
    setup_scene, setup_world, setup_camera, export_glb,
    material_pbr, material_simple, material_emissive,
    add_modifiers, randomize_vertices, add_volume_mist,
)

# ── 参数 ──────────────────────────────────────────────────
PARAMS = {}
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if args:
    with open(args[0]) as f:
        PARAMS = json.load(f)

output_path = PARAMS.get("output_path", "/tmp/desert_ruins.glb")
scale = PARAMS.get("scale", 1.0)
time_of_day = PARAMS.get("time_of_day", "day")

if time_of_day == "sunset":
    sun_energy, sun_color, sky_color, mist_color = 5.0, (1.0, 0.55, 0.25), (0.7, 0.35, 0.12), (0.95, 0.75, 0.4)
elif time_of_day == "night":
    sun_energy, sun_color, sky_color, mist_color = 0.4, (0.2, 0.3, 0.5), (0.01, 0.02, 0.04), (0.05, 0.06, 0.1)
else:
    sun_energy, sun_color, sky_color, mist_color = 6.0, (1.0, 0.92, 0.75), (0.55, 0.65, 0.8), (0.9, 0.78, 0.55)

s = scale

setup_scene()

# ═══════════════════════════════════════════════════════════
# PBR 材质
# ═══════════════════════════════════════════════════════════
sand_mat = material_pbr("Sand", "Ground054", roughness_override=0.9,
                         scale=(10, 10, 1), bump_strength=0.05, displacement_scale=0.04)
stone_mat = material_pbr("Stone", "Rock023", roughness_override=0.7,
                          scale=(4, 4, 4), bump_strength=0.06, displacement_scale=0.05)
marble_mat = material_pbr("Marble", "Marble008", roughness_override=0.4,
                           scale=(3, 3, 3), bump_strength=0.03, displacement_scale=0.02)
dark_stone = material_pbr("DarkStone", "Rock032", roughness_override=0.6,
                           scale=(3, 3, 3), bump_strength=0.06, displacement_scale=0.04)
rubble_mat = material_simple("Rubble", (0.55, 0.38, 0.22), roughness=0.75, metallic=0.1)
gold_mat = material_simple("Gold", (0.85, 0.65, 0.15), roughness=0.2, metallic=0.9)

# ═══════════════════════════════════════════════════════════
# 沙地地形
# ═══════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=18*s, location=(0, 0, -0.03*s))
ground = bpy.context.active_object
ground.name = "DesertFloor"
ground.data.materials.append(sand_mat)

# 地形起伏 — 3 个位移修改器叠加 (large/medium/small ripples)
for name, ns, ds in [("Dunes", 0.3, 0.50), ("Ripples", 1.2, 0.12), ("Micro", 3.0, 0.03)]:
    disp_mod = ground.modifiers.new(name, 'DISPLACE')
    disp_tex = bpy.data.textures.new(f"{name}Tex", 'CLOUDS')
    disp_tex.noise_scale = ns
    disp_mod.texture = disp_tex
    disp_mod.strength = ds * s
    disp_mod.mid_level = 0.45

add_modifiers(ground, subsurf=1, bevel=False)

# ═══════════════════════════════════════════════════════════
# 金字塔 (主建筑)
# ═══════════════════════════════════════════════════════════
px, py = 0, 0
p_base = 3.0 * s
p_height = 2.5 * s

bpy.ops.mesh.primitive_cone_add(
    vertices=4, radius1=p_base * 0.707, radius2=0, depth=p_height,
    location=(px, py, p_height / 2)
)
pyramid = bpy.context.active_object
pyramid.name = "Pyramid"
pyramid.rotation_euler = (0, 0, math.radians(45))
pyramid.data.materials.append(marble_mat)
add_modifiers(pyramid, bevel=True, bevel_width=0.04*s)

# 金字塔底座平台
bpy.ops.mesh.primitive_cube_add(size=1, location=(px, py, 0.08*s))
bpy.ops.transform.resize(value=(p_base * 0.85, p_base * 0.85, 0.12*s))
base = bpy.context.active_object
base.name = "PyramidBase"
base.data.materials.append(dark_stone)
add_modifiers(base, bevel=True, bevel_width=0.03*s)

# ═══════════════════════════════════════════════════════════
# 方尖碑
# ═══════════════════════════════════════════════════════════
obelisk_cfgs = [
    (px + p_base * 0.9, py + p_base * 0.5, 0.3*s, 2.0*s),
    (px - p_base * 0.8, py + p_base * 0.6, 0.25*s, 1.6*s),
    (px + p_base * 0.6, py - p_base * 0.7, 0.22*s, 1.4*s),
    (px - p_base * 0.7, py - p_base * 0.5, 0.28*s, 1.8*s),
]
for i, (ox, oy, rad, oh) in enumerate(obelisk_cfgs):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8, radius=rad, depth=oh,
        location=(ox, oy, oh / 2)
    )
    pillar = bpy.context.active_object
    pillar.name = f"Obelisk_{i}"
    pillar.data.materials.append(stone_mat)
    add_modifiers(pillar, bevel=True, bevel_width=0.02*s)

    # 碑顶小金字塔
    bpy.ops.mesh.primitive_cone_add(
        vertices=4, radius1=rad * 1.6, radius2=0.02*s, depth=rad * 4,
        location=(ox, oy, oh + rad * 2)
    )
    top = bpy.context.active_object
    top.name = f"ObeliskTop_{i}"
    top.rotation_euler = (0, 0, math.radians(45))
    top.data.materials.append(marble_mat)

# ═══════════════════════════════════════════════════════════
# 石柱群
# ═══════════════════════════════════════════════════════════
for i in range(5):
    cx = px - p_base * 0.5 + i * 0.7 * s
    cy = py - p_base * 0.85
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=0.12*s, depth=random.uniform(1.0, 1.8)*s,
        location=(cx, cy, random.uniform(0.6, 1.0)*s)
    )
    col = bpy.context.active_object
    col.name = f"Column_{i}"
    col.data.materials.append(stone_mat)
    randomize_vertices(col, 0.03*s)
    add_modifiers(col, bevel=True, bevel_width=0.02*s)

# 第二排
for i in range(4):
    cx = px + p_base * 0.45 + i * 0.65 * s
    cy = py - p_base * 0.95
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=10, radius=0.14*s, depth=random.uniform(0.8, 1.5)*s,
        location=(cx, cy, random.uniform(0.45, 0.85)*s)
    )
    col2 = bpy.context.active_object
    col2.name = f"ColumnB_{i}"
    col2.data.materials.append(marble_mat)
    randomize_vertices(col2, 0.02*s)
    add_modifiers(col2, bevel=True, bevel_width=0.015*s)

# ═══════════════════════════════════════════════════════════
# 风化碎石散布
# ═══════════════════════════════════════════════════════════
for _ in range(40):
    rx = random.uniform(-5.5, 5.5) * s
    ry = random.uniform(-4.5, 4.5) * s
    # 避开金字塔核心区
    if abs(rx - px) < p_base * 0.9 and abs(ry - py) < p_base * 0.9:
        continue
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=2, radius=random.uniform(0.04, 0.2)*s,
        location=(rx, ry, random.uniform(0.02, 0.12)*s)
    )
    rubble = bpy.context.active_object
    rubble.name = f"Rubble_{_}"
    rubble.data.materials.append(rubble_mat if random.random() < 0.7 else stone_mat)
    randomize_vertices(rubble, 0.08*s)

# ═══════════════════════════════════════════════════════════
# 黄金圣甲虫雕像 (金字塔前方)
# ═══════════════════════════════════════════════════════════
sx, sy = px + p_base * 0.9, py
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25*s, location=(sx, sy, 0.35*s))
body = bpy.context.active_object
body.name = "ScarabBody"
body.data.materials.append(gold_mat)
bpy.ops.transform.resize(value=(0.8, 0.6, 0.4))

bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.06*s, depth=0.15*s,
                                     location=(sx, sy, 0.08*s))
base_pedestal = bpy.context.active_object
base_pedestal.name = "ScarabPedestal"
base_pedestal.data.materials.append(marble_mat)

# ═══════════════════════════════════════════════════════════
# 沙丘纹理路径
# ═══════════════════════════════════════════════════════════
for t in range(10):
    tx = px - p_base * 0.6 + t * 0.3 * s
    ty = py - p_base * 0.9
    bpy.ops.mesh.primitive_plane_add(
        size=0.22*s, location=(tx, ty + random.uniform(-0.1, 0.1)*s, 0.005*s)
    )
    path_stone = bpy.context.active_object
    path_stone.name = f"PathStone_{t}"
    path_stone.data.materials.append(dark_stone)
    path_stone.rotation_euler = (0, 0, random.uniform(0, 6.28))

# ═══════════════════════════════════════════════════════════
# 光照
# ═══════════════════════════════════════════════════════════
setup_world(sky_color=sky_color, strength=0.6)

bpy.ops.object.light_add(type='SUN', location=(10, -8, 12))
sun = bpy.context.active_object
sun.name = "DesertSun"
sun.data.energy = sun_energy
sun.data.angle = 0.04
sun.data.color = sun_color

bpy.ops.object.light_add(type='AREA', location=(-6, 4, 3))
fill = bpy.context.active_object
fill.name = "FillLight"
fill.data.energy = sun_energy * 0.15
fill.data.size = 6 * s

# 火炬点光源
for _ in range(3):
    tx = px + random.uniform(-3, 3) * s
    ty = py + random.uniform(-3, 3) * s
    bpy.ops.object.light_add(type='POINT', location=(tx, ty, 0.5*s))
    torch = bpy.context.active_object
    torch.name = f"Torch_{_}"
    torch.data.energy = 25 if time_of_day != "night" else 80
    torch.data.color = (1.0, 0.6, 0.2)

add_volume_mist(density=0.02 if time_of_day == "day" else 0.04, color=mist_color)

# ═══════════════════════════════════════════════════════════
# 相机
# ═══════════════════════════════════════════════════════════
setup_camera(location=(8*s, -7*s, 5*s), look_at=(px, py, p_height / 2), fov=50)

export_glb(output_path)
