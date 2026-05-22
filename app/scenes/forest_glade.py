"""
CineAnchor 场景: 森林空地

Blender 无头运行: blender --background --python forest_glade.py -- params.json
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

output_path = PARAMS.get("output_path", "/tmp/forest_glade.glb")
scale = PARAMS.get("scale", 1.0)
time_of_day = PARAMS.get("time_of_day", "day")

if time_of_day == "sunset":
    sun_energy, sun_color, sky_color, mist_color = 3.0, (1.0, 0.6, 0.3), (0.6, 0.4, 0.3), (0.7, 0.55, 0.4)
elif time_of_day == "night":
    sun_energy, sun_color, sky_color, mist_color = 0.2, (0.1, 0.2, 0.4), (0.01, 0.02, 0.04), (0.03, 0.04, 0.06)
else:
    sun_energy, sun_color, sky_color, mist_color = 4.0, (1.0, 0.9, 0.7), (0.35, 0.5, 0.6), (0.8, 0.85, 0.7)

s = scale

setup_scene()

# ═══════════════════════════════════════════════════════════
# PBR 材质
# ═══════════════════════════════════════════════════════════
grass_mat = material_pbr("Grass", "Ground044", roughness_override=0.7,
                          scale=(8, 8, 1), bump_strength=0.05, displacement_scale=0.04)
moss_mat = material_pbr("Moss", "Moss001", roughness_override=0.75,
                         scale=(6, 6, 1), bump_strength=0.04, displacement_scale=0.03)
bark_mat = material_pbr("Bark", "Wood045", roughness_override=0.7,
                         scale=(4, 4, 4), bump_strength=0.06, displacement_scale=0.04)
leaf_mat = material_simple("Leaves", (0.15, 0.45, 0.1), roughness=0.65, metallic=0.0)
leaf_dark = material_simple("LeavesDark", (0.08, 0.28, 0.05), roughness=0.7, metallic=0.0)
stone_path = material_pbr("PathStone", "Rock023", roughness_override=0.7,
                           scale=(3, 3, 3), bump_strength=0.05, displacement_scale=0.03)
flower_mat = material_emissive("FlowerGlow", (0.9, 0.7, 0.9), strength=1.5)

# ═══════════════════════════════════════════════════════════
# 草地地面
# ═══════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_grid_add(x_subdivisions=50, y_subdivisions=50, size=14*s, location=(0, 0, -0.02*s))
ground = bpy.context.active_object
ground.name = "ForestFloor"
ground.data.materials.append(grass_mat)

# 地形起伏
for name, ns, ds in [("Hills", 0.25, 0.25), ("Mounds", 1.0, 0.08)]:
    disp_mod = ground.modifiers.new(name, 'DISPLACE')
    disp_tex = bpy.data.textures.new(f"{name}Tex", 'CLOUDS')
    disp_tex.noise_scale = ns
    disp_mod.texture = disp_tex
    disp_mod.strength = ds * s
    disp_mod.mid_level = 0.4

add_modifiers(ground, subsurf=1, bevel=False)

# ═══════════════════════════════════════════════════════════
# 大树干 (随机分布)
# ═══════════════════════════════════════════════════════════
tree_cfgs = [
    (0, 0.5*s, 0.25*s, 2.8*s),
    (-3.0*s, -1.0*s, 0.3*s, 3.2*s),
    (3.5*s, -0.5*s, 0.22*s, 2.5*s),
    (-2.5*s, 2.5*s, 0.28*s, 2.9*s),
    (4.0*s, 2.0*s, 0.2*s, 2.2*s),
    (-4.0*s, -2.5*s, 0.35*s, 3.5*s),
    (1.5*s, -3.0*s, 0.26*s, 2.6*s),
    (2.5*s, 3.0*s, 0.24*s, 2.4*s),
]

for i, (tx, ty, trad, th) in enumerate(tree_cfgs):
    # 树干
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=trad, depth=th,
        location=(tx, ty, th / 2)
    )
    trunk = bpy.context.active_object
    trunk.name = f"TreeTrunk_{i}"
    trunk.data.materials.append(bark_mat)
    randomize_vertices(trunk, 0.02*s)
    add_modifiers(trunk, bevel=True, bevel_width=0.01*s)

    # 树冠 (多个 cone + sphere)
    crown_start = th * 0.55
    for tier in range(4):
        tier_rad = trad * random.uniform(3.5, 5.5) * (1 - tier * 0.2)
        bpy.ops.mesh.primitive_cone_add(
            vertices=14, radius1=tier_rad, radius2=0.01*s,
            depth=tier_rad * 1.4,
            location=(tx + random.uniform(-0.1, 0.1)*s,
                      ty + random.uniform(-0.1, 0.1)*s,
                      crown_start + tier * tier_rad * 0.7)
        )
        crown = bpy.context.active_object
        crown.name = f"TreeCrown_{i}_{tier}"
        crown.data.materials.append(leaf_mat if tier % 2 == 0 else leaf_dark)
        randomize_vertices(crown, 0.04*s)

    # 树冠顶部球
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=2, radius=trad * random.uniform(2.5, 3.5),
        location=(tx, ty, crown_start + 4 * trad * 0.7)
    )
    top_crown = bpy.context.active_object
    top_crown.name = f"TreeTop_{i}"
    top_crown.data.materials.append(leaf_mat)
    randomize_vertices(top_crown, 0.06*s)

# ═══════════════════════════════════════════════════════════
# 灌木丛
# ═══════════════════════════════════════════════════════════
for _ in range(15):
    bx = random.uniform(-5, 5) * s
    by = random.uniform(-4, 4) * s
    # 避开大树
    too_close = any(
        math.sqrt((bx - tx)**2 + (by - ty)**2) < trad * 3.0
        for tx, ty, trad, _ in [(c[0], c[1], c[2], c[3]) for c in tree_cfgs]
    )
    if too_close:
        continue
    for j in range(random.randint(3, 7)):
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=2, radius=random.uniform(0.1, 0.25)*s,
            location=(bx + random.uniform(-0.2, 0.2)*s,
                      by + random.uniform(-0.2, 0.2)*s,
                      random.uniform(0.1, 0.4)*s)
        )
        bush = bpy.context.active_object
        bush.name = f"Bush_{_}_{j}"
        bush.data.materials.append(leaf_dark if j % 2 else leaf_mat)
        randomize_vertices(bush, 0.05*s)

# ═══════════════════════════════════════════════════════════
# 小径石头
# ═══════════════════════════════════════════════════════════
path_waypoints = [(-3.5*s, 0.5*s), (-1.5*s, 1.0*s), (0*s, 0.8*s), (2.0*s, 0.2*s), (4.0*s, -0.5*s)]
for t in range(30):
    frac = t / 29
    idx = min(int(frac * (len(path_waypoints) - 1)), len(path_waypoints) - 2)
    sub = frac * (len(path_waypoints) - 1) - idx
    sx = path_waypoints[idx][0] * (1 - sub) + path_waypoints[idx + 1][0] * sub
    sy = path_waypoints[idx][1] * (1 - sub) + path_waypoints[idx + 1][1] * sub
    sx += random.uniform(-0.2, 0.2) * s
    sy += random.uniform(-0.15, 0.15) * s

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8, radius=random.uniform(0.08, 0.16)*s, depth=0.03*s,
        location=(sx, sy, 0.015*s)
    )
    step = bpy.context.active_object
    step.name = f"PathStep_{t}"
    step.data.materials.append(stone_path)
    randomize_vertices(step, 0.01*s)

# ═══════════════════════════════════════════════════════════
# 空地中央 (阳光斑驳处)
# ═══════════════════════════════════════════════════════════
glade_center = (0.5*s, 0.3*s)
# 环形石圈
for i in range(8):
    angle = i * math.pi * 2 / 8
    gx = glade_center[0] + math.cos(angle) * 0.8*s
    gy = glade_center[1] + math.sin(angle) * 0.8*s
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8, radius=0.1*s, depth=0.22*s,
        location=(gx, gy, 0.11*s)
    )
    ring_stone = bpy.context.active_object
    ring_stone.name = f"RingStone_{i}"
    ring_stone.data.materials.append(stone_path)
    add_modifiers(ring_stone, bevel=True, bevel_width=0.01*s)

# 花丛
for _ in range(20):
    fx = glade_center[0] + random.uniform(-1.0, 1.0) * s
    fy = glade_center[1] + random.uniform(-1.0, 1.0) * s
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=1, radius=random.uniform(0.02, 0.05)*s,
        location=(fx, fy, random.uniform(0.04, 0.1)*s)
    )
    flower = bpy.context.active_object
    flower.name = f"Flower_{_}"
    flower.data.materials.append(flower_mat)

# ═══════════════════════════════════════════════════════════
# 倒木
# ═══════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_cylinder_add(
    vertices=12, radius=0.15*s, depth=3.5*s,
    location=(-2.0*s, -3.0*s, 0.08*s)
)
log = bpy.context.active_object
log.name = "FallenLog"
log.rotation_euler = (0, 0, math.radians(15))
log.data.materials.append(bark_mat)
randomize_vertices(log, 0.03*s)
add_modifiers(log, bevel=True, bevel_width=0.01*s)

# 树干上的苔藓
for _ in range(6):
    bpy.ops.mesh.primitive_plane_add(
        size=random.uniform(0.1, 0.25)*s,
        location=(-2.0*s + random.uniform(-1.5, 1.5)*s, -3.0*s + random.uniform(-0.15, 0.15)*s, 0.2*s)
    )
    log_moss = bpy.context.active_object
    log_moss.name = f"LogMoss_{_}"
    log_moss.data.materials.append(moss_mat)
    log_moss.rotation_euler = (random.uniform(0, 0.3), random.uniform(0, 0.3), random.uniform(0, 6.28))

# ═══════════════════════════════════════════════════════════
# 阳光光束 (体积光 — 用 emissive 薄锥模拟)
# ═══════════════════════════════════════════════════════════
for _ in range(5):
    lx = glade_center[0] + random.uniform(-0.8, 0.8) * s
    ly = glade_center[1] + random.uniform(-0.8, 0.8) * s
    bpy.ops.mesh.primitive_cone_add(
        vertices=6, radius1=0.5*s, radius2=0.05*s, depth=3.5*s,
        location=(lx, ly, 2.0*s)
    )
    beam = bpy.context.active_object
    beam.name = f"LightBeam_{_}"
    beam.data.materials.append(material_simple(f"BeamMat_{_}", (1.0, 0.95, 0.75), roughness=1.0, metallic=0.0))
    beam.rotation_euler = (math.radians(15), 0, random.uniform(0, 6.28))

# ═══════════════════════════════════════════════════════════
# 光照
# ═══════════════════════════════════════════════════════════
setup_world(sky_color=sky_color, strength=0.5)

bpy.ops.object.light_add(type='SUN', location=(6, -8, 10))
sun = bpy.context.active_object
sun.name = "Sun"
sun.data.energy = sun_energy
sun.data.angle = 0.06
sun.data.color = sun_color

bpy.ops.object.light_add(type='AREA', location=(-3, 3, 4))
fill = bpy.context.active_object
fill.name = "FillLight"
fill.data.energy = sun_energy * 0.2
fill.data.size = 5 * s

# 空地微弱点光 (模拟阳光斑驳)
bpy.ops.object.light_add(type='POINT', location=(glade_center[0], glade_center[1], 2.5*s))
spot = bpy.context.active_object
spot.name = "GladeGlow"
spot.data.energy = 12 if time_of_day != "night" else 40
spot.data.color = (1.0, 0.9, 0.7)

add_volume_mist(density=0.018 if time_of_day == "day" else 0.03, color=mist_color)

# ═══════════════════════════════════════════════════════════
# 相机
# ═══════════════════════════════════════════════════════════
setup_camera(location=(7*s, -6*s, 4*s), look_at=(glade_center[0], glade_center[1], 1.5*s), fov=55)

export_glb(output_path)
