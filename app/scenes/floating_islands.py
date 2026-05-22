"""
CineAnchor 场景: 浮岛天空仙境

Blender 无头运行: blender --background --python floating_islands.py -- params.json
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

output_path = PARAMS.get("output_path", "/tmp/floating_islands.glb")
scale = PARAMS.get("scale", 1.0)
time_of_day = PARAMS.get("time_of_day", "day")

if time_of_day == "sunset":
    sun_energy, sun_color, sky_color, mist_color = 4.0, (1.0, 0.7, 0.4), (0.7, 0.35, 0.55), (0.9, 0.7, 0.6)
elif time_of_day == "night":
    sun_energy, sun_color, sky_color, mist_color = 0.5, (0.15, 0.2, 0.4), (0.01, 0.02, 0.05), (0.1, 0.1, 0.15)
else:
    sun_energy, sun_color, sky_color, mist_color = 4.5, (1.0, 0.95, 0.85), (0.45, 0.6, 0.85), (0.85, 0.82, 0.78)

s = scale

setup_scene()

# ═══════════════════════════════════════════════════════════
# PBR 材质
# ═══════════════════════════════════════════════════════════
island_rock = material_pbr("IslandRock", "Rock023", roughness_override=0.65,
                            scale=(6, 6, 6), bump_strength=0.07, displacement_scale=0.06)
cliff_mat = material_pbr("Cliff", "Rock032", roughness_override=0.55,
                          scale=(4, 4, 4), bump_strength=0.08, displacement_scale=0.07)
grass_mat = material_pbr("Grass", "Ground044", roughness_override=0.7,
                          scale=(5, 5, 1), bump_strength=0.04, displacement_scale=0.03)
moss_mat = material_pbr("Moss", "Moss001", roughness_override=0.8,
                         scale=(3, 3, 1), bump_strength=0.03, displacement_scale=0.02)
crystal_mat = material_simple("Crystal", (0.15, 0.5, 0.7), roughness=0.1, metallic=0.3)
water_mat = material_simple("Waterfall", (0.2, 0.5, 0.8), roughness=0.05, metallic=0.4)
vine_mat = material_pbr("Vine", "Wood045", roughness_override=0.6,
                         scale=(4, 4, 4), bump_strength=0.04, displacement_scale=0.02)
cloud_mat = material_simple("Cloud", (0.9, 0.92, 0.95), roughness=1.0, metallic=0.0)

# ═══════════════════════════════════════════════════════════
# 主浮岛 — 倒锥形岩体
# ═══════════════════════════════════════════════════════════
islands = [
    {"pos": (0, 0, 0), "radius": 2.8*s, "height": 1.8*s, "name": "MainIsland"},
    {"pos": (4.5*s, 1.5*s, -1.5*s), "radius": 1.6*s, "height": 1.0*s, "name": "EastIsland"},
    {"pos": (-3.8*s, -0.8*s, -1.0*s), "radius": 2.0*s, "height": 1.2*s, "name": "WestIsland"},
    {"pos": (1.8*s, -3.5*s, -2.5*s), "radius": 1.2*s, "height": 0.8*s, "name": "SouthIsland"},
    {"pos": (-1.2*s, 3.5*s, -0.8*s), "radius": 1.0*s, "height": 0.7*s, "name": "NorthIsland"},
]

for ix, iy, iz, rad, h, name in [(d["pos"][0], d["pos"][1], d["pos"][2], d["radius"], d["height"], d["name"]) for d in islands]:
    # 岛体 — 倒锥
    bpy.ops.mesh.primitive_cone_add(
        vertices=24, radius1=rad, radius2=rad * 0.35, depth=h,
        location=(ix, iy, iz)
    )
    island = bpy.context.active_object
    island.name = f"{name}_Core"
    island.data.materials.append(cliff_mat if name != "MainIsland" else island_rock)
    randomize_vertices(island, 0.08 * s)
    add_modifiers(island, subsurf=2, bevel=True, bevel_width=0.03*s)

    # 顶部平台
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24, radius=rad * 0.85, depth=0.08*s,
        location=(ix, iy, iz + h/2)
    )
    platform = bpy.context.active_object
    platform.name = f"{name}_Top"
    platform.data.materials.append(grass_mat)

    # 地表小植被
    for _ in range(12 if name == "MainIsland" else 6):
        px = ix + random.uniform(-rad*0.7, rad*0.7)
        py = iy + random.uniform(-rad*0.7, rad*0.7)
        bpy.ops.mesh.primitive_cone_add(
            vertices=5, radius1=random.uniform(0.03, 0.08)*s,
            radius2=0, depth=random.uniform(0.08, 0.2)*s,
            location=(px, py, iz + h/2 + 0.04*s)
        )
        grass_blade = bpy.context.active_object
        grass_blade.name = f"Grass_{name}_{_}"
        grass_blade.data.materials.append(moss_mat)

# ═══════════════════════════════════════════════════════════
# 水晶/宝石装饰
# ═══════════════════════════════════════════════════════════
for _ in range(8):
    cx = random.uniform(-1.8, 1.8) * s
    cy = random.uniform(-1.8, 1.8) * s
    cz = 0.9*s + random.uniform(0, 0.5)*s
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=2, radius=random.uniform(0.06, 0.14)*s,
        location=(cx, cy, cz)
    )
    crystal = bpy.context.active_object
    crystal.name = f"Crystal_{_}"
    crystal.data.materials.append(crystal_mat)

# ═══════════════════════════════════════════════════════════
# 瀑布 (从主岛边缘流下)
# ═══════════════════════════════════════════════════════════
waterfall_origins = [
    (1.5*s, 0.5*s, 0.85*s),
    (-1.0*s, -1.2*s, 0.85*s),
    (0.8*s, -1.5*s, 0.85*s),
]
for i, (wx, wy, wz) in enumerate(waterfall_origins):
    for seg in range(5):
        sz = wz - seg * 0.7 * s
        bpy.ops.mesh.primitive_plane_add(
            size=0.25*s,
            location=(wx + random.uniform(-0.05, 0.05)*s,
                      wy + random.uniform(-0.05, 0.05)*s,
                      max(0.05*s, sz))
        )
        drop = bpy.context.active_object
        drop.name = f"Waterfall_{i}_{seg}"
        drop.rotation_euler = (random.uniform(0, 0.3), random.uniform(0, 0.3), random.uniform(0, 6.28))
        drop.data.materials.append(water_mat)

# ═══════════════════════════════════════════════════════════
# 藤蔓桥 (连接主岛和东岛)
# ═══════════════════════════════════════════════════════════
bridge_start = (1.5*s, 0.3*s, 0.88*s)
bridge_end = (3.2*s, 1.2*s, 0.4*s)
bridge_segs = 6
for t in range(bridge_segs):
    frac = t / (bridge_segs - 1)
    bx = bridge_start[0] * (1 - frac) + bridge_end[0] * frac
    by = bridge_start[1] * (1 - frac) + bridge_end[1] * frac
    bz = bridge_start[2] * (1 - frac) + bridge_end[2] * frac - 0.08*s * math.sin(frac * math.pi)
    # 桥板
    bpy.ops.mesh.primitive_plane_add(
        size=0.35*s * (1 - abs(frac - 0.5) * 0.5),
        location=(bx, by, bz)
    )
    plank = bpy.context.active_object
    plank.name = f"BridgePlank_{t}"
    plank.data.materials.append(vine_mat)
    angle = math.atan2(bridge_end[1] - bridge_start[1], bridge_end[0] - bridge_start[0])
    plank.rotation_euler = (0, 0, angle)

# 桥索
for side in [-1, 1]:
    for t in range(bridge_segs + 1):
        frac = t / bridge_segs
        bx = bridge_start[0] * (1 - frac) + bridge_end[0] * frac + side * 0.12*s
        by = bridge_start[1] * (1 - frac) + bridge_end[1] * frac + side * 0.12*s
        bz = bridge_start[2] * (1 - frac) + bridge_end[2] * frac + 0.12*s
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=1, radius=0.03*s, location=(bx, by, bz)
        )
        knot = bpy.context.active_object
        knot.name = f"BridgeKnot_{side}_{t}"
        knot.data.materials.append(vine_mat)

# ═══════════════════════════════════════════════════════════
# 云层粒子 (散布在各个高度)
# ═══════════════════════════════════════════════════════════
for _ in range(20):
    clx = random.uniform(-6, 6) * s
    cly = random.uniform(-5, 5) * s
    clz = random.uniform(-3, 3) * s
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=2, radius=random.uniform(0.15, 0.5)*s,
        location=(clx, cly, clz)
    )
    cloud = bpy.context.active_object
    cloud.name = f"Cloud_{_}"
    cloud.data.materials.append(cloud_mat)
    randomize_vertices(cloud, 0.15*s)

# ═══════════════════════════════════════════════════════════
# 远处小浮岛 (背景)
# ═══════════════════════════════════════════════════════════
for _ in range(6):
    fx = random.uniform(-3, 3) * s
    fy = random.uniform(-2, 2) * s
    fz = 2.5*s + random.uniform(0, 2)*s
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=3, radius=random.uniform(0.12, 0.3)*s,
        location=(fx, fy, fz)
    )
    far = bpy.context.active_object
    far.name = f"FarIslet_{_}"
    far.data.materials.append(island_rock)
    randomize_vertices(far, 0.1*s)

# ═══════════════════════════════════════════════════════════
# 光照
# ═══════════════════════════════════════════════════════════
setup_world(sky_color=sky_color, strength=0.8)

bpy.ops.object.light_add(type='SUN', location=(12, -5, 8))
sun = bpy.context.active_object
sun.name = "Sun"
sun.data.energy = sun_energy
sun.data.angle = 0.05
sun.data.color = sun_color

bpy.ops.object.light_add(type='AREA', location=(-5, 3, 4))
fill = bpy.context.active_object
fill.name = "FillLight"
fill.data.energy = sun_energy * 0.25
fill.data.size = 5 * s

# 水晶点光源
for _ in range(3):
    bpy.ops.object.light_add(type='POINT',
        location=(random.uniform(-1.5, 1.5)*s, random.uniform(-1.5, 1.5)*s, 1.0*s))
    pt = bpy.context.active_object
    pt.name = f"CrystalGlow_{_}"
    pt.data.energy = 15 if time_of_day != "night" else 40
    pt.data.color = (0.3, 0.6, 0.9)

add_volume_mist(density=0.012 if time_of_day == "day" else 0.025, color=mist_color)

# ═══════════════════════════════════════════════════════════
# 相机
# ═══════════════════════════════════════════════════════════
setup_camera(location=(9*s, -6*s, 5*s), look_at=(0, 0, 1.2*s), fov=55)

export_glb(output_path)
