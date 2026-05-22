"""
CineAnchor 场景: 日式禅园 v3 (PBR 纹理版)

使用 ambientCG CC0 贴图集实现游戏级材质效果
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

output_path = PARAMS.get("output_path", "/tmp/zen_garden.glb")
scale = PARAMS.get("scale", 1.0)
time_of_day = PARAMS.get("time_of_day", "day")

if time_of_day == "sunset":
    sun_energy, sun_color, sky_color, mist_color = 2.5, (1.0, 0.75, 0.45), (0.6, 0.4, 0.25), (0.8, 0.6, 0.4)
elif time_of_day == "night":
    sun_energy, sun_color, sky_color, mist_color = 0.3, (0.2, 0.3, 0.5), (0.02, 0.03, 0.06), (0.05, 0.05, 0.1)
else:
    sun_energy, sun_color, sky_color, mist_color = 3.5, (1.0, 0.95, 0.85), (0.4, 0.55, 0.75), (0.8, 0.8, 0.75)

s = scale

setup_scene()

# ═══════════════════════════════════════════════════════════
# PBR 材质 (使用 ambientCG 纹理)
# ═══════════════════════════════════════════════════════════
sand_mat = material_pbr("Sand", "Ground054", roughness_override=0.85,
                         scale=(8, 8, 1), bump_strength=0.04, displacement_scale=0.03)

gravel_mat = material_pbr("Gravel", "Ground044", roughness_override=0.75,
                           scale=(10, 10, 1), bump_strength=0.05, displacement_scale=0.04)

stone_mat = material_pbr("Stone", "Rock023", roughness_override=0.6,
                          scale=(3, 3, 3), bump_strength=0.06, displacement_scale=0.05)

dark_stone_mat = material_pbr("DarkStone", "Rock032", roughness_override=0.5,
                               scale=(3, 3, 3), bump_strength=0.06, displacement_scale=0.04)

moss_mat = material_pbr("Moss", "Moss001", roughness_override=0.8,
                         scale=(5, 5, 1), bump_strength=0.03, displacement_scale=0.02)

bamboo_mat = material_pbr("Bamboo", "Wood045", roughness_override=0.55,
                           scale=(2, 2, 2), bump_strength=0.02, displacement_scale=0.01)

marble_mat = material_pbr("Marble", "Marble008", roughness_override=0.35,
                           scale=(2, 2, 2), bump_strength=0.02, displacement_scale=0.01)

water_mat = material_simple("Water", (0.08, 0.22, 0.35), roughness=0.06, metallic=0.5)

# ═══════════════════════════════════════════════════════════
# 地形 — 带置换的微地形
# ═══════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_grid_add(x_subdivisions=50, y_subdivisions=50, size=14*s, location=(0, 0, -0.02*s))
ground = bpy.context.active_object
ground.name = "Ground"
ground.data.materials.append(sand_mat)
# 云纹理置换
disp_mod = ground.modifiers.new("Terrain", 'DISPLACE')
disp_tex = bpy.data.textures.new("TerrainTex", 'CLOUDS')
disp_tex.noise_scale = 0.5
disp_mod.texture = disp_tex
disp_mod.strength = 0.06 * s
disp_mod.mid_level = 0.35

add_modifiers(ground, subsurf=1, bevel=False)

# ═══════════════════════════════════════════════════════════
# 碎石地面 (局部)
# ═══════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_plane_add(size=5*s, location=(-2*s, 2.5*s, 0.005*s))
gravel_area = bpy.context.active_object
gravel_area.name = "GravelArea"
gravel_area.data.materials.append(gravel_mat)
disp2 = gravel_area.modifiers.new("GravelDisp", 'DISPLACE')
disp2_tex = bpy.data.textures.new("GravelTex", 'CLOUDS')
disp2_tex.noise_scale = 0.8
disp2.texture = disp2_tex
disp2.strength = 0.04 * s

# ═══════════════════════════════════════════════════════════
# 石组 — PBR 材质 + 自然变形
# ═══════════════════════════════════════════════════════════
stone_configs = [
    (1.8*s, 1.0*s, 0.20*s, 0.5*s,  stone_mat),
    (-2.0*s, 1.3*s, 0.25*s, 0.6*s, stone_mat),
    (2.5*s, -1.8*s, 0.16*s, 0.4*s, stone_mat),
    (-1.5*s, -2.2*s, 0.22*s, 0.55*s, stone_mat),
    (0.5*s, 3.0*s, 0.28*s, 0.65*s, stone_mat),
    (-3.0*s, 0.0*s, 0.18*s, 0.45*s, dark_stone_mat),
    (3.5*s, 2.5*s, 0.14*s, 0.35*s, dark_stone_mat),
    (-0.5*s, -0.5*s, 0.10*s, 0.28*s, stone_mat),
]

for idx, (x, y, z, rad, mat) in enumerate(stone_configs):
    # 主石
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=rad, location=(x, y, z))
    stone = bpy.context.active_object
    stone.name = f"Stone_{idx}"
    randomize_vertices(stone, strength=rad * 0.25)
    stone.data.materials.append(mat)
    add_modifiers(stone, subsurf=2, bevel=True, bevel_width=0.02*s)

    # 小石围绕
    for j in range(random.randint(3, 6)):
        angle = random.uniform(0, 6.28)
        dist = rad * random.uniform(1.3, 2.4)
        sx, sy = x + math.cos(angle) * dist, y + math.sin(angle) * dist
        sr = rad * random.uniform(0.06, 0.18)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=sr, location=(sx, sy, sr * 0.5))
        peb = bpy.context.active_object
        peb.name = f"Pebble_{idx}_{j}"
        peb.data.materials.append(gravel_mat if j % 2 else mat)

    # 苔藓片
    for j in range(random.randint(1, 3)):
        mx = x + random.uniform(-rad * 0.7, rad * 0.7)
        my = y + random.uniform(-rad * 0.7, rad * 0.7)
        bpy.ops.mesh.primitive_plane_add(size=rad * random.uniform(0.25, 0.55), location=(mx, my, z + rad * 0.3))
        mp = bpy.context.active_object
        mp.name = f"Moss_{idx}_{j}"
        mp.rotation_euler = (random.uniform(0, 0.2), random.uniform(0, 0.2), random.uniform(0, 6.28))
        mp.data.materials.append(moss_mat)

# ═══════════════════════════════════════════════════════════
# 枯山水砂纹
# ═══════════════════════════════════════════════════════════
for cx, cy, rad in [(2.0*s, 1.2*s, 1.6*s), (-2.2*s, 1.5*s, 2.0*s), (2.8*s, -2.0*s, 1.4*s)]:
    for i in range(8):
        r = (i + 1) * rad / 8
        segs = max(24, int(r * 18))
        bpy.ops.mesh.primitive_circle_add(vertices=segs, radius=r, location=(cx, cy, 0.006*s))
        ring = bpy.context.active_object
        ring.name = f"Ripple_{int(cx)}_{int(cy)}_{i}"
        ring.data.materials.append(gravel_mat)

# ═══════════════════════════════════════════════════════════
# 竹栅栏
# ═══════════════════════════════════════════════════════════
fence_y = -5.0 * s
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.05*s, depth=2.2*s, location=(0, fence_y, 1.1*s))
post = bpy.context.active_object
post.name = "BambooPost"
post.data.materials.append(bamboo_mat)
add_modifiers(post, bevel=True, bevel_width=0.01*s)
randomize_vertices(post, 0.02*s)

arr = post.modifiers.new("FenceArray", 'ARRAY')
arr.count = 13
arr.relative_offset_displace = (0.35 * s, 0, 0)

# 横梁
for h in [1.6*s, 0.5*s]:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8, radius=0.035*s, depth=12 * 0.35 * s,
        location=(0, fence_y, h), rotation=(0, math.radians(90), 0))
    beam = bpy.context.active_object
    beam.name = f"Beam_{h}"
    beam.data.materials.append(bamboo_mat)
    add_modifiers(beam, bevel=True, bevel_width=0.01*s)

# ═══════════════════════════════════════════════════════════
# 石灯笼 (PBR 大理石 + 自发光)
# ═══════════════════════════════════════════════════════════
lx, ly = 3.8*s, -3.0*s

parts = [
    ("Cylinder", (lx, ly, 0.06*s), 0.32*s, 0.12*s),
    ("Cylinder", (lx, ly, 0.65*s), 0.1*s, 1.0*s),
    ("Cylinder", (lx, ly, 1.2*s), 0.22*s, 0.08*s),
]
for ptype, loc, rad, depth in parts:
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=rad, depth=depth, location=loc)
    obj = bpy.context.active_object
    obj.name = f"LanternPart_{ptype}"
    obj.data.materials.append(marble_mat)
    add_modifiers(obj, bevel=True, bevel_width=0.015*s)

# 灯室 (自发光)
bpy.ops.mesh.primitive_cube_add(size=0.28*s, location=(lx, ly, 1.45*s))
chamber = bpy.context.active_object
chamber.name = "LanternChamber"
chamber.data.materials.append(material_emissive("LanternGlow", (1.0, 0.8, 0.5), strength=4.0))
add_modifiers(chamber, bevel=True, bevel_width=0.02*s)

# 屋顶
bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.35*s, radius2=0.0, depth=0.35*s, location=(lx, ly, 1.75*s))
roof = bpy.context.active_object
roof.name = "LanternRoof"
roof.data.materials.append(marble_mat)
add_modifiers(roof, bevel=True, bevel_width=0.02*s)

# 宝珠
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07*s, location=(lx, ly, 1.98*s))
jewel = bpy.context.active_object
jewel.name = "LanternJewel"
jewel.data.materials.append(marble_mat)

# ═══════════════════════════════════════════════════════════
# 水池
# ═══════════════════════════════════════════════════════════
px, py = -3.2*s, 3.2*s
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1.1*s, depth=0.04*s, location=(px, py, 0.02*s))
pond = bpy.context.active_object
pond.name = "Pond"
pond.data.materials.append(water_mat)

for i in range(14):
    angle = i * math.pi * 2 / 14
    ex = px + math.cos(angle) * 1.18*s
    ey = py + math.sin(angle) * 1.18*s
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=random.uniform(0.07, 0.14)*s, location=(ex, ey, 0.04*s))
    es = bpy.context.active_object
    es.name = f"PondEdge_{i}"
    es.data.materials.append(stone_mat)

# ═══════════════════════════════════════════════════════════
# 松树
# ═══════════════════════════════════════════════════════════
tx, ty = -4.0*s, -0.5*s
bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.1*s, depth=1.8*s, location=(tx, ty, 0.9*s))
trunk = bpy.context.active_object
trunk.name = "PineTrunk"
trunk.data.materials.append(bamboo_mat)
randomize_vertices(trunk, 0.015*s)
add_modifiers(trunk, bevel=True, bevel_width=0.01*s)

for tier in range(4):
    bpy.ops.mesh.primitive_cone_add(
        vertices=14, radius1=(0.65 - tier * 0.12)*s, radius2=0.02*s,
        depth=0.65*s, location=(tx, ty, (1.1 + tier * 0.4)*s))
    cone = bpy.context.active_object
    cone.name = f"PineCrown_{tier}"
    cone.data.materials.append(moss_mat)
    randomize_vertices(cone, 0.03*s)
    add_modifiers(cone, bevel=True, bevel_width=0.01*s)

# ═══════════════════════════════════════════════════════════
# 踏脚石小径
# ═══════════════════════════════════════════════════════════
for t in range(6):
    sx = px - 2.0*s + t * 0.65*s
    sy = py + 0.2*s + math.sin(t * 0.8) * 0.25*s
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.15*s, depth=0.03*s, location=(sx, sy, 0.015*s))
    step = bpy.context.active_object
    step.name = f"StepStone_{t}"
    step.data.materials.append(marble_mat)
    randomize_vertices(step, 0.02*s)
    add_modifiers(step, bevel=True, bevel_width=0.01*s)

# ═══════════════════════════════════════════════════════════
# 地表散布
# ═══════════════════════════════════════════════════════════
for i in range(30):
    gx = random.uniform(-5.5, 5.5) * s
    gy = random.uniform(-4.5, 4.5) * s
    if abs(gx - px) < 1.5*s and abs(gy - py) < 1.5*s: continue
    if abs(gx - lx) < 0.6*s and abs(gy - ly) < 0.6*s: continue

    gtype = random.choice(['grass', 'pebble', 'moss_patch'])
    if gtype == 'grass':
        bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=random.uniform(0.02, 0.05)*s,
                                         radius2=0, depth=random.uniform(0.08, 0.2)*s,
                                         location=(gx, gy, random.uniform(0.02, 0.06)*s))
        obj = bpy.context.active_object
        obj.data.materials.append(moss_mat)
    elif gtype == 'pebble':
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.02, 0.06)*s,
                                               location=(gx, gy, random.uniform(0.01, 0.03)*s))
        obj = bpy.context.active_object
        obj.data.materials.append(gravel_mat)
    else:
        bpy.ops.mesh.primitive_plane_add(size=random.uniform(0.05, 0.15)*s, location=(gx, gy, 0.01*s))
        obj = bpy.context.active_object
        obj.data.materials.append(moss_mat)
        obj.rotation_euler = (random.uniform(0, 0.3), random.uniform(0, 0.3), random.uniform(0, 6.28))
    obj.name = f"Detail_{gtype}_{i}"

# ═══════════════════════════════════════════════════════════
# 光照与氛围
# ═══════════════════════════════════════════════════════════
setup_world(sky_color=sky_color, strength=0.7)

# 主光
bpy.ops.object.light_add(type='SUN', location=(10, -6, 10))
sun = bpy.context.active_object
sun.name = "Sun"
sun.data.energy = sun_energy
sun.data.angle = 0.06
sun.data.color = sun_color

# 补光
bpy.ops.object.light_add(type='AREA', location=(-4, 3, 3))
fill = bpy.context.active_object
fill.name = "FillLight"
fill.data.energy = sun_energy * 0.2
fill.data.size = 3 * s

# 灯笼点光
bpy.ops.object.light_add(type='POINT', location=(lx, ly, 1.45*s))
lamp = bpy.context.active_object
lamp.name = "LanternPoint"
lamp.data.energy = 20 if time_of_day != "night" else 60
lamp.data.color = (1.0, 0.75, 0.4)

# 体积雾
add_volume_mist(density=0.015 if time_of_day == "day" else 0.03, color=mist_color)

# ═══════════════════════════════════════════════════════════
# 相机
# ═══════════════════════════════════════════════════════════
setup_camera(location=(8*s, -7*s, 5*s), look_at=(0.5*s, 0.2*s, 0.7*s), fov=50)

export_glb(output_path)
