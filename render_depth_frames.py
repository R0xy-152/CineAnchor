"""
Blender depth map renderer — renders raw Z-depth to EXR, then normalizes to 0-255 PNG.
Run: blender --background --python render_depth_frames.py
"""
import bpy
import os
import math
import random
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "demo_depth_frames")

def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for tex in list(bpy.data.textures):
        bpy.data.textures.remove(tex)

def setup_depth_render(camera, near, far):
    """Configure Blender to render raw Z-depth pass to EXR."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = 768
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.image_settings.color_mode = 'BW'

    # Fastest render
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 0
    scene.cycles.diffuse_bounces = 0
    scene.cycles.glossy_bounces = 0
    scene.cycles.transmission_bounces = 0
    scene.cycles.volume_bounces = 0

    camera.data.clip_start = near
    camera.data.clip_end = far

    # Enable Z pass
    view_layer = scene.view_layers["ViewLayer"]
    view_layer.use_pass_z = True

    # ── Compositor: just pass through Z depth ──
    scene.use_nodes = True
    ng = bpy.data.node_groups.new('DepthComposite', 'CompositorNodeTree')
    scene.compositing_node_group = ng
    nodes = ng.nodes
    links = ng.links

    rl = nodes.new('CompositorNodeRLayers')
    rl.location = (0, 0)

    # Normalize node: stretches input to 0-1 range per frame
    normalize = nodes.new('CompositorNodeNormalize')
    normalize.location = (200, 0)

    comp = nodes.new('CompositorNodeComposite')
    comp.location = (400, 0)

    links.new(rl.outputs['Depth'], normalize.inputs[0])
    links.new(normalize.outputs[0], comp.inputs[0])


def create_animated_camera(start_pos, end_pos, look_at, frames=24):
    """Create animated camera always looking at a target."""
    bpy.ops.object.camera_add(location=start_pos)
    cam = bpy.context.active_object
    cam.name = "DepthCam"

    bpy.ops.object.empty_add(type='PLAIN_AXES', location=look_at)
    target = bpy.context.active_object
    target.name = "CamTarget"

    bpy.context.view_layer.objects.active = cam
    bpy.ops.object.constraint_add(type='TRACK_TO')
    cam.constraints["Track To"].target = target
    cam.constraints["Track To"].track_axis = 'TRACK_NEGATIVE_Z'
    cam.constraints["Track To"].up_axis = 'UP_Y'

    scene = bpy.context.scene
    scene.frame_start = 0
    scene.frame_end = frames - 1

    cam.location = start_pos
    cam.keyframe_insert(data_path="location", frame=0)
    cam.location = end_pos
    cam.keyframe_insert(data_path="location", frame=frames - 1)

    return cam, target


# ═══════════════════════════════════════════════════════════
# Scene builders (simplified geometry — no textures needed)
# ═══════════════════════════════════════════════════════════

def build_zen_garden():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=20, y_subdivisions=20, size=12, location=(0, 0, 0))
    bpy.context.active_object.name = "Ground"
    for i in range(8):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=random.uniform(0.2, 0.6),
                                               location=(random.uniform(-4, 4), random.uniform(-3, 3), random.uniform(0.1, 0.3)))
        bpy.context.active_object.name = f"Rock_{i}"
        bpy.context.active_object.scale = (1, 1, random.uniform(0.5, 1.0))
    for i in range(5):
        x, y = random.uniform(-5, 5), random.uniform(-4, 4)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=2.0, location=(x, y, 1.0))
        bpy.context.active_object.name = f"Trunk_{i}"
        bpy.ops.mesh.primitive_cone_add(radius1=0.8, radius2=0.0, depth=1.5, location=(x, y, 2.2))
        bpy.context.active_object.name = f"Crown_{i}"
    bpy.ops.mesh.primitive_circle_add(radius=1.5, location=(1.5, -1.5, 0.01))
    bpy.context.active_object.name = "Pond"
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.5, -1.5, 0.15))
    b = bpy.context.active_object
    b.name = "Bridge"; b.scale = (0.4, 2.0, 0.08)
    for i in range(8):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=0.03,
                                             location=(-2 + i * 0.5, 0.5 + math.sin(i) * 0.3, 0.015))
        bpy.context.active_object.name = f"Path_{i}"
    return create_animated_camera((7, -6, 4), (0, 0, 2.5), (0, 0, 0.5))


def build_scifi_corridor():
    L = 15
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -1.5)); bpy.context.active_object.scale = (3, L, 0.1)
    bpy.context.active_object.name = "Floor"
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 2.5)); bpy.context.active_object.scale = (3, L, 0.1)
    bpy.context.active_object.name = "Ceiling"
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-2.5, 0, 0.5)); bpy.context.active_object.scale = (0.1, L, 2.5)
    bpy.context.active_object.name = "Wall_L"
    bpy.ops.mesh.primitive_cube_add(size=1, location=(2.5, 0, 0.5)); bpy.context.active_object.scale = (0.1, L, 2.5)
    bpy.context.active_object.name = "Wall_R"
    for i in range(8):
        z_pos = -6 + i * 1.5
        for sx in [-1.8, 1.8]:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=4, location=(sx, z_pos, 0.5))
            bpy.context.active_object.name = f"Pillar_{i}_{'L' if sx < 0 else 'R'}"
    for i in range(20):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -7 + i * 0.7, -1.35)); bpy.context.active_object.scale = (2.5, 0.05, 0.05)
        bpy.context.active_object.name = f"Ridge_{i}"
    for i in range(10):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -7 + i * 1.5, 2.35)); bpy.context.active_object.scale = (2.5, 0.08, 0.08)
        bpy.context.active_object.name = f"Beam_{i}"
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -7, 0.5)); bpy.context.active_object.scale = (3, 0.1, 2.5)
    bpy.context.active_object.name = "EndWall"
    return create_animated_camera((0.5, 6, 1.0), (0.2, -5, 0.8), (0, 0, 0.5))


def build_floating_islands():
    islands = [(0, 0, 4, 3.0), (5, -2, 3, 2.0), (-4, 1, 5, 2.5), (3, 4, 2, 1.5), (-3, -3, 3.5, 1.8)]
    for idx, (cx, cy, cz, size) in enumerate(islands):
        bpy.ops.mesh.primitive_cylinder_add(radius=size, depth=0.3, location=(cx, cy, cz))
        bpy.context.active_object.name = f"Island_{idx}"
        bpy.ops.mesh.primitive_cone_add(radius1=size * 0.8, radius2=size * 0.3, depth=2.0, location=(cx, cy, cz - 1.2))
        bpy.context.active_object.name = f"Base_{idx}"
    for _ in range(12):
        ix = random.choice([i[0] for i in islands]) + random.uniform(-0.8, 0.8)
        iy = random.choice([i[1] for i in islands]) + random.uniform(-0.8, 0.8)
        iz = random.choice([i[2] for i in islands]) + 0.2
        bpy.ops.mesh.primitive_cone_add(radius1=0.1, radius2=0.0, depth=random.uniform(0.5, 1.5), location=(ix, iy, iz + 0.3))
        bpy.context.active_object.name = f"Crystal_{_}"
    for _ in range(15):
        cx, cy = random.uniform(-8, 8), random.uniform(-6, 6)
        cz = random.choice([i[2] for i in islands]) + random.uniform(-1.5, 1.5)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=random.uniform(0.3, 0.8), location=(cx, cy, cz))
        bpy.context.active_object.name = f"Cloud_{_}"; bpy.context.active_object.scale = (1, 1, 0.2)
    return create_animated_camera((10, -8, 8), (-3, 2, 4), (0, 0, 3.5))


def build_desert_ruins():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=30, y_subdivisions=30, size=20, location=(0, 0, -0.1))
    bpy.context.active_object.name = "Ground"
    dm = bpy.context.active_object.modifiers.new("Dunes", 'DISPLACE')
    dt = bpy.data.textures.new("DuneTex", 'CLOUDS'); dt.noise_scale = 0.6
    dm.texture = dt; dm.strength = 0.3; dm.mid_level = 0.3
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=3, radius2=0, depth=4, location=(0, 0, 2))
    bpy.context.active_object.name = "Pyramid"; bpy.context.active_object.rotation_euler = (0, 0, math.pi / 4)
    for i in range(8):
        a = i * math.pi / 4; r = 4.5
        bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=3, location=(r * math.cos(a), r * math.sin(a), 1.5))
        bpy.context.active_object.name = f"Col_{i}"
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 6; r = 6
        bpy.ops.mesh.primitive_cube_add(size=1, location=(r * math.cos(a), r * math.sin(a), 1.2))
        bpy.context.active_object.name = f"Obel_{i}"; bpy.context.active_object.scale = (0.3, 0.3, 2.5)
    for _ in range(30):
        x, y = random.uniform(-7, 7), random.uniform(-7, 7)
        if abs(x) < 1 and abs(y) < 1: continue
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.05, 0.2), location=(x, y, random.uniform(0.02, 0.1)))
        bpy.context.active_object.name = f"Rubble_{_}"
    return create_animated_camera((10, -8, 6), (-2, 2, 3), (0, 0, 1.5))


def build_forest_glade():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=30, y_subdivisions=30, size=16, location=(0, 0, 0))
    bpy.context.active_object.name = "Ground"
    dm = bpy.context.active_object.modifiers.new("Terrain", 'DISPLACE')
    dt = bpy.data.textures.new("ForestTex", 'CLOUDS'); dt.noise_scale = 0.4
    dm.texture = dt; dm.strength = 0.15; dm.mid_level = 0.3
    for _ in range(15):
        x, y = random.uniform(-6, 6), random.uniform(-6, 6)
        if abs(x) < 1.5 and abs(y) < 1.5: x = random.choice([random.uniform(-6, -2), random.uniform(2, 6)])
        h = random.uniform(1.5, 3.5)
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=random.uniform(0.08, 0.2), depth=h, location=(x, y, h / 2))
        bpy.context.active_object.name = f"Trunk_{_}"
        for tier in range(random.randint(2, 4)):
            bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=random.uniform(0.5, 1.0), radius2=0.01,
                                             depth=random.uniform(0.6, 1.2), location=(x, y, h * 0.6 + tier * 0.6))
            bpy.context.active_object.name = f"Crown_{_}_{tier}"
    for i in range(12):
        a = i * math.pi / 6; r = 1.8
        bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=random.uniform(0.3, 0.8),
                                             location=(r * math.cos(a), r * math.sin(a), random.uniform(0.15, 0.4)))
        bpy.context.active_object.name = f"Stone_{i}"
    for i in range(10):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=0.04, location=(-4 + i * 0.5, 1.5 + math.sin(i * 0.5) * 0.4, 0.02))
        bpy.context.active_object.name = f"Path_{i}"
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=3, location=(2, -1.5, 0.08))
    bpy.context.active_object.name = "Log"; bpy.context.active_object.rotation_euler = (0, 0, math.pi / 6)
    return create_animated_camera((6, -6, 4), (1, 1, 1.5), (0, 0, 1.0))


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

SCENES = {
    "zen_garden":       (build_zen_garden,       0.5, 30.0),
    "scifi_corridor":   (build_scifi_corridor,   0.3, 25.0),
    "floating_islands": (build_floating_islands, 0.5, 40.0),
    "desert_ruins":     (build_desert_ruins,     0.5, 35.0),
    "forest_glade":     (build_forest_glade,     0.3, 25.0),
}

for scene_name, (builder, near, far) in SCENES.items():
    print(f"\n{'='*60}")
    print(f"  Building: {scene_name} (near={near}, far={far})")
    print(f"{'='*60}")

    clear_scene()
    camera, target = builder()

    scene_dir = os.path.join(OUTPUT_DIR, scene_name)
    os.makedirs(scene_dir, exist_ok=True)

    # Clear old frames
    for f in os.listdir(scene_dir):
        if f.endswith('.png') or f.endswith('.exr'):
            os.remove(os.path.join(scene_dir, f))

    setup_depth_render(camera, near, far)

    # Render 24 frames to EXR
    for frame in range(24):
        bpy.context.scene.frame_set(frame)
        exr_path = os.path.join(scene_dir, f"frame_{frame:04d}.exr")
        bpy.context.scene.render.filepath = exr_path
        bpy.ops.render.render(write_still=True)
    print(f"  {scene_name}: 24 EXR frames rendered")

print("\nBlender rendering complete. Run normalize_depth_frames.py to convert EXR to PNG.")
