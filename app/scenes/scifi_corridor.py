"""
CineAnchor 场景: 科幻走廊

Blender 无头运行: blender --background --python scifi_corridor.py -- params.json
"""

import sys
import os
import json
import math
import random
import bpy

sys.path.insert(0, os.environ.get('CINEANCHOR_ROOT', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.scene_helpers import (
    setup_scene, setup_world, setup_camera, export_glb,
    material_procedural, material_simple, material_emissive,
    add_modifiers, randomize_vertices, add_volume_mist,
)

# ── 参数 ──────────────────────────────────────────────────
PARAMS = {}
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if args:
    with open(args[0]) as f:
        PARAMS = json.load(f)

output_path = PARAMS.get("output_path", "/tmp/scifi_corridor.glb")
scale = PARAMS.get("scale", 1.0)
accent = PARAMS.get("accent_color", "蓝")

COLORS = {
    "蓝": (0.08, 0.35, 0.95), "红": (0.95, 0.08, 0.15),
    "绿": (0.05, 0.9, 0.25), "紫": (0.55, 0.1, 0.9),
    "橙": (1.0, 0.45, 0.04), "金": (1.0, 0.75, 0.08),
}
neon = COLORS.get(accent, COLORS["蓝"])
s = scale

setup_scene()

# ═══════════════════════════════════════════════════════════
# 材质
# ═══════════════════════════════════════════════════════════
metal_dark = material_procedural("MetalDark", (0.08, 0.08, 0.1), (0.14, 0.14, 0.17),
                                  roughness=0.25, metallic=0.85, scale=2.0, bump_strength=0.02)
metal_panel = material_procedural("MetalPanel", (0.15, 0.16, 0.19), (0.2, 0.22, 0.25),
                                   roughness=0.3, metallic=0.8, scale=3.0, bump_strength=0.015)
floor_mat = material_simple("Floor", (0.06, 0.07, 0.09), roughness=0.35, metallic=0.85)
neon_mat = material_emissive("Neon", neon, strength=8.0)
pipe_mat = material_simple("Pipe", (0.2, 0.2, 0.22), roughness=0.45, metallic=0.85)
panel_detail = material_simple("PanelDetail", (0.12, 0.13, 0.15), roughness=0.3, metallic=0.9)

# ═══════════════════════════════════════════════════════════
# 走廊主体
# ═══════════════════════════════════════════════════════════
corridor_len = 16 * s
corridor_w = 3.2 * s
corridor_h = 4.0 * s

# 地板 — 带分段的金属格栅
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
bpy.ops.transform.resize(value=(corridor_len, corridor_w, 1))
floor = bpy.context.active_object
floor.name = "Floor"
floor.data.materials.append(floor_mat)
# 地板分割 (增加几何细节)
bpy.ops.object.editmode_toggle()
bpy.ops.mesh.subdivide(number_cuts=20)
bpy.ops.object.editmode_toggle()

# 天花板 — 带肋条
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, corridor_h))
bpy.ops.transform.resize(value=(corridor_len, corridor_w, 1))
ceiling = bpy.context.active_object
ceiling.name = "Ceiling"
ceiling.data.materials.append(metal_dark)

# 天花板横梁 (每 1.5m 一根)
for i in range(-5, 6):
    x = i * 1.5 * s
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, corridor_h - 0.08*s))
    bpy.ops.transform.resize(value=(0.06*s, corridor_w * 0.9, 0.15*s))
    beam = bpy.context.active_object
    beam.name = f"CeilingBeam_{i}"
    beam.data.materials.append(metal_panel)
    add_modifiers(beam, bevel=True, bevel_width=0.015*s)

# 左墙
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -corridor_w/2, corridor_h/2))
bpy.ops.transform.resize(value=(corridor_len, 1, corridor_h))
bpy.ops.object.editmode_toggle()
bpy.ops.mesh.subdivide(number_cuts=16)
bpy.ops.object.editmode_toggle()
wall_l = bpy.context.active_object
wall_l.name = "Wall_L"
wall_l.rotation_euler = (math.radians(90), 0, 0)
wall_l.data.materials.append(metal_panel)

# 右墙
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, corridor_w/2, corridor_h/2))
bpy.ops.transform.resize(value=(corridor_len, 1, corridor_h))
bpy.ops.object.editmode_toggle()
bpy.ops.mesh.subdivide(number_cuts=16)
bpy.ops.object.editmode_toggle()
wall_r = bpy.context.active_object
wall_r.name = "Wall_R"
wall_r.rotation_euler = (math.radians(90), 0, 0)
wall_r.data.materials.append(metal_panel)

# ═══════════════════════════════════════════════════════════
# 结构肋柱 (每隔一定距离)
# ═══════════════════════════════════════════════════════════
for i in range(-5, 6):
    x = i * 1.5 * s
    for side in [-1, 1]:
        y = side * (corridor_w/2 - 0.02*s)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8, radius=0.1*s, depth=corridor_h,
            location=(x, y, corridor_h/2)
        )
        pillar = bpy.context.active_object
        pillar.name = f"Pillar_{i}_{side}"
        pillar.data.materials.append(metal_dark)
        add_modifiers(pillar, bevel=True, bevel_width=0.01*s)

# 斜撑
for i in range(-4, 5):
    x = i * 1.5 * s + 0.75*s
    for side in [-1, 1]:
        y = side * (corridor_w/2 - 0.05*s)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, corridor_h * 0.35))
        bpy.ops.transform.resize(value=(0.03*s, 0.03*s, corridor_h * 0.25))
        brace = bpy.context.active_object
        brace.name = f"Brace_{i}_{side}"
        brace.rotation_euler = (math.radians(25), 0, 0)
        brace.data.materials.append(metal_panel)

# ═══════════════════════════════════════════════════════════
# 霓虹灯带系统
# ═══════════════════════════════════════════════════════════

# 墙面上方灯带 (连续)
for side in [-1, 1]:
    y = side * (corridor_w/2 - 0.04*s)
    z = corridor_h * 0.38
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, z))
    bpy.ops.transform.resize(value=(corridor_len * 0.85, 0.015*s, 0.04*s))
    strip = bpy.context.active_object
    strip.name = f"NeonStrip_Wall_{side}"
    strip.data.materials.append(neon_mat)

# 墙面下方灯带
for side in [-1, 1]:
    y = side * (corridor_w/2 - 0.04*s)
    z = corridor_h * 0.12
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, z))
    bpy.ops.transform.resize(value=(corridor_len * 0.85, 0.015*s, 0.03*s))
    strip = bpy.context.active_object
    strip.name = f"NeonStrip_Floor_{side}"
    strip.data.materials.append(neon_mat)

# 天花板中心灯带
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, corridor_h - 0.03*s))
bpy.ops.transform.resize(value=(corridor_len * 0.8, corridor_w * 0.05, 0.02*s))
ceiling_neon = bpy.context.active_object
ceiling_neon.name = "CeilingNeon"
ceiling_neon.data.materials.append(neon_mat)

# 竖直线性光 (每隔一段)
for i in range(-6, 7):
    x = i * 1.2 * s
    for side in [-1, 1]:
        y = side * (corridor_w/2 - 0.03*s)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, corridor_h * 0.5))
        bpy.ops.transform.resize(value=(0.015*s, 0.01*s, corridor_h * 0.3))
        vlight = bpy.context.active_object
        vlight.name = f"VertLight_{i}_{side}"
        vlight.data.materials.append(neon_mat)

# ═══════════════════════════════════════════════════════════
# 地板六边形格栅
# ═══════════════════════════════════════════════════════════
for i in range(-5, 6):
    for j in range(-1, 2):
        x = i * 1.4 * s + (j % 2) * 0.7 * s
        y = j * 1.2 * s
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=6, radius=0.52*s, depth=0.008*s,
            location=(x, y, 0.004*s)
        )
        hex = bpy.context.active_object
        hex.name = f"HexTile_{i}_{j}"
        hex.data.materials.append(metal_panel)

# ═══════════════════════════════════════════════════════════
# 天花板设备/管道
# ═══════════════════════════════════════════════════════════
for i in range(-5, 6, 2):
    x = i * 1.2 * s
    # 粗管道
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=10, radius=0.08*s, depth=corridor_w * 0.85,
        location=(x, 0, corridor_h - 0.3*s),
        rotation=(0, math.radians(90), 0)
    )
    pipe = bpy.context.active_object
    pipe.name = f"CeilingPipe_{i}"
    pipe.data.materials.append(pipe_mat)

# 细管道阵列
for i in range(-6, 7):
    x = i * 1.0 * s
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=6, radius=0.03*s, depth=corridor_w * 0.8,
        location=(x, 0, corridor_h - 0.5*s),
        rotation=(0, math.radians(90), 0)
    )
    thin_pipe = bpy.context.active_object
    thin_pipe.name = f"ThinPipe_{i}"
    thin_pipe.data.materials.append(pipe_mat)

# ═══════════════════════════════════════════════════════════
# 终端全息屏幕
# ═══════════════════════════════════════════════════════════
screen_x = corridor_len/2 - 0.05*s
bpy.ops.mesh.primitive_plane_add(size=2.0*s, location=(screen_x, 0, corridor_h/2))
screen = bpy.context.active_object
screen.name = "HoloScreen"
screen.rotation_euler = (0, math.radians(90), 0)
screen.data.materials.append(neon_mat)

# 屏幕框
bpy.ops.mesh.primitive_cube_add(size=1, location=(screen_x - 0.02*s, 0, corridor_h/2 - 1.05*s))
bpy.ops.transform.resize(value=(0.04*s, 1.1*s, 0.04*s))
frame_b = bpy.context.active_object
frame_b.name = "ScreenFrameBottom"
frame_b.data.materials.append(metal_dark)

bpy.ops.mesh.primitive_cube_add(size=1, location=(screen_x - 0.02*s, 0, corridor_h/2 + 1.05*s))
bpy.ops.transform.resize(value=(0.04*s, 1.1*s, 0.04*s))
frame_t = bpy.context.active_object
frame_t.name = "ScreenFrameTop"
frame_t.data.materials.append(metal_dark)

# ═══════════════════════════════════════════════════════════
# 侧墙细节面板
# ═══════════════════════════════════════════════════════════
for i in range(-4, 5, 2):
    x = i * 1.8 * s
    for side in [-1, 1]:
        y = side * (corridor_w/2 - 0.08*s)
        bpy.ops.mesh.primitive_plane_add(size=0.6*s, location=(x, y, corridor_h * 0.7))
        panel = bpy.context.active_object
        panel.name = f"DetailPanel_{i}_{side}"
        panel.rotation_euler = (0, 0 if side > 0 else math.radians(180), 0)
        panel.data.materials.append(panel_detail)

# ═══════════════════════════════════════════════════════════
# 光照
# ═══════════════════════════════════════════════════════════
setup_world(sky_color=(0.005, 0.005, 0.01), strength=0.15)

# 顶部长条面光
bpy.ops.object.light_add(type='AREA', location=(0, 0, corridor_h - 0.2*s))
main_light = bpy.context.active_object
main_light.name = "MainAreaLight"
main_light.data.energy = 60
main_light.data.size = corridor_len * 0.6
main_light.data.color = (0.95, 0.95, 1.0)

# 霓虹点光源阵列 (环境氛围)
for i in range(-4, 5):
    x = i * 2.0 * s
    bpy.ops.object.light_add(type='POINT', location=(x, 0, corridor_h * 0.55))
    pt = bpy.context.active_object
    pt.name = f"AmbientPoint_{i}"
    pt.data.energy = 8
    pt.data.color = neon

# 屏幕前方点光
bpy.ops.object.light_add(type='POINT', location=(screen_x - 0.3*s, 0, corridor_h/2))
screen_light = bpy.context.active_object
screen_light.name = "ScreenGlow"
screen_light.data.energy = 20
screen_light.data.color = neon

# 微弱的体积雾
add_volume_mist(density=0.01, color=(0.6, 0.6, 0.8))

# ═══════════════════════════════════════════════════════════
# 相机
# ═══════════════════════════════════════════════════════════
setup_camera(
    location=(corridor_len/2 - 0.8*s, -corridor_w * 0.65, 1.5*s),
    look_at=(0, 0, corridor_h * 0.4),
    fov=60
)

export_glb(output_path)
