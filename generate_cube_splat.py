import numpy as np
from plyfile import PlyData, PlyElement


def create_cube_splat(output_path="test_scene.ply", num_points=20000):
    """
    生成一个立方体表面的 3DGS PLY 文件。
    高斯点分布在六个面上（非体积填充），确保深度图产生清晰的表面边缘，
    ControlNet-Depth 才能正确识别几何结构。
    """
    print(f"Generating surface-only 3DGS cube with {num_points} points...")

    # ---- 六个面均匀采样 ----
    points_per_face = num_points // 6
    remainder = num_points % 6

    faces = []
    for face_idx in range(6):
        n = points_per_face + (1 if face_idx < remainder else 0)
        # 在 [0,1]² 上均匀采样
        u = np.random.rand(n)
        v = np.random.rand(n)
        uv = np.stack([u * 2 - 1, v * 2 - 1], axis=-1)  # [-1, 1]²

        # 映射到六个面
        ones = np.ones(n)
        if face_idx == 0:   # +Z face: z=1
            pts = np.column_stack([uv[:, 0], uv[:, 1], ones])
        elif face_idx == 1: # -Z face: z=-1
            pts = np.column_stack([uv[:, 0], uv[:, 1], -ones])
        elif face_idx == 2: # +X face: x=1
            pts = np.column_stack([ones, uv[:, 0], uv[:, 1]])
        elif face_idx == 3: # -X face: x=-1
            pts = np.column_stack([-ones, uv[:, 0], uv[:, 1]])
        elif face_idx == 4: # +Y face: y=1
            pts = np.column_stack([uv[:, 0], ones, uv[:, 1]])
        else:               # -Y face: y=-1
            pts = np.column_stack([uv[:, 0], -ones, uv[:, 1]])
        faces.append(pts)

    xyz = np.concatenate(faces, axis=0).astype(np.float32)
    np.random.shuffle(xyz)  # 打乱以避免面边界伪影

    # ---- 颜色：XYZ 映射到 RGB ----
    rgb = (xyz + 1) / 2.0
    C0 = 0.28209479177387814
    f_dc = ((rgb - 0.5) / C0).astype(np.float32)

    # ---- 缩放：exp(-2.0) ≈ 0.135 — 紧密排列但保持锐利边缘 ----
    scale = np.full((len(xyz), 3), -2.0, dtype=np.float32)

    # ---- 旋转：单位四元数 ----
    rot = np.zeros((len(xyz), 4), dtype=np.float32)
    rot[:, 0] = 1.0

    # ---- 不透明度：sigmoid(15) ≈ 0.9999997 — 接近完全不透明 ----
    opacity = np.full((len(xyz), 1), 15.0, dtype=np.float32)

    # ---- 组装 PLY ----
    dtype = [
        ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
        ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
        ('f_dc_0', 'f4'), ('f_dc_1', 'f4'), ('f_dc_2', 'f4'),
        ('opacity', 'f4'),
        ('scale_0', 'f4'), ('scale_1', 'f4'), ('scale_2', 'f4'),
        ('rot_0', 'f4'), ('rot_1', 'f4'), ('rot_2', 'f4'), ('rot_3', 'f4')
    ]

    elements = np.empty(len(xyz), dtype=dtype)
    elements['x'] = xyz[:, 0]
    elements['y'] = xyz[:, 1]
    elements['z'] = xyz[:, 2]
    elements['nx'] = 0
    elements['ny'] = 0
    elements['nz'] = 0
    elements['f_dc_0'] = f_dc[:, 0]
    elements['f_dc_1'] = f_dc[:, 1]
    elements['f_dc_2'] = f_dc[:, 2]
    elements['opacity'] = opacity[:, 0]
    elements['scale_0'] = scale[:, 0]
    elements['scale_1'] = scale[:, 1]
    elements['scale_2'] = scale[:, 2]
    elements['rot_0'] = rot[:, 0]
    elements['rot_1'] = rot[:, 1]
    elements['rot_2'] = rot[:, 2]
    elements['rot_3'] = rot[:, 3]

    PlyData([PlyElement.describe(elements, 'vertex')]).write(output_path)
    print(f"Saved {len(xyz)} surface points → {output_path}")


def create_large_cube_splat(output_path="scene_large_cube.ply", num_points=30000):
    """6x6x6 大立方体，表面均匀采样，尺度更紧以保持锐利边缘。"""
    print(f"Generating LARGE cube (6x6x6) with {num_points} surface points...")

    points_per_face = num_points // 6
    remainder = num_points % 6
    half = 3.0  # half-size

    faces = []
    for face_idx in range(6):
        n = points_per_face + (1 if face_idx < remainder else 0)
        u = np.random.rand(n) * 2 - 1  # [-1, 1]
        v = np.random.rand(n) * 2 - 1
        ones = np.ones(n)

        if face_idx == 0:
            pts = np.column_stack([u * half, v * half, ones * half])
        elif face_idx == 1:
            pts = np.column_stack([u * half, v * half, -ones * half])
        elif face_idx == 2:
            pts = np.column_stack([ones * half, u * half, v * half])
        elif face_idx == 3:
            pts = np.column_stack([-ones * half, u * half, v * half])
        elif face_idx == 4:
            pts = np.column_stack([u * half, ones * half, v * half])
        else:
            pts = np.column_stack([u * half, -ones * half, v * half])
        faces.append(pts)

    xyz = np.concatenate(faces, axis=0).astype(np.float32)
    np.random.shuffle(xyz)

    _write_ply(xyz, scale_log=-2.5, opacity_log=15.0, output_path=output_path)


def create_multi_object_splat(output_path="scene_multi.ply", num_points=30000):
    """多物体场景：3 个立方体 + 1 个球体，分散在 [-4,4]^3 空间。"""
    print(f"Generating MULTI-OBJECT scene with {num_points} points...")

    # 物体定义: (type, center, size/radius, point_count)
    objects = [
        ("cube", (0.0, 0.0, 0.0), 1.8, 12000),      # 中心大立方体
        ("cube", (3.5, 1.5, -1.0), 1.0, 6000),       # 右前小立方体
        ("cube", (-3.0, -1.0, 2.0), 1.2, 6000),      # 左后小立方体
        ("sphere", (1.0, -2.5, -2.0), 1.0, 6000),    # 下方球体
    ]

    parts = []
    for obj_type, center, size, count in objects:
        cx, cy, cz = center
        if obj_type == "cube":
            # 六面均匀采样
            per_face = count // 6
            rem = count % 6
            for fi in range(6):
                n = per_face + (1 if fi < rem else 0)
                u = np.random.rand(n) * 2 - 1
                v = np.random.rand(n) * 2 - 1
                ones = np.ones(n) * size
                if fi == 0:
                    pts = np.column_stack([u * size + cx, v * size + cy, ones + cz])
                elif fi == 1:
                    pts = np.column_stack([u * size + cx, v * size + cy, -ones + cz])
                elif fi == 2:
                    pts = np.column_stack([ones + cx, u * size + cy, v * size + cz])
                elif fi == 3:
                    pts = np.column_stack([-ones + cx, u * size + cy, v * size + cz])
                elif fi == 4:
                    pts = np.column_stack([u * size + cx, ones + cy, v * size + cz])
                else:
                    pts = np.column_stack([u * size + cx, -ones + cy, v * size + cz])
                parts.append(pts)
        else:
            # 球体：单位球面随机采样 + 缩放 + 平移
            pts = np.random.randn(count, 3).astype(np.float32)
            pts = pts / np.linalg.norm(pts, axis=1, keepdims=True) * size
            pts = pts + np.array([cx, cy, cz])
            parts.append(pts)

    xyz = np.concatenate(parts, axis=0).astype(np.float32)
    np.random.shuffle(xyz)

    _write_ply(xyz, scale_log=-2.0, opacity_log=12.0, output_path=output_path)


def _write_ply(xyz, scale_log, opacity_log, output_path):
    """通用 PLY 写入：XYZ→RGB 颜色映射 + 固定尺度/不透明度/旋转。"""
    n = len(xyz)

    # 颜色：坐标映射到 RGB
    xyz_min = xyz.min(axis=0)
    xyz_max = xyz.max(axis=0)
    xyz_range = xyz_max - xyz_min
    xyz_range[xyz_range == 0] = 1.0
    rgb_norm = (xyz - xyz_min) / xyz_range
    rgb = (rgb_norm * 0.6 + 0.2).clip(0, 1)  # 避免纯黑纯白

    C0 = 0.28209479177387814
    f_dc = ((rgb - 0.5) / C0).astype(np.float32)
    scale = np.full((n, 3), scale_log, dtype=np.float32)
    rot = np.zeros((n, 4), dtype=np.float32)
    rot[:, 0] = 1.0  # 单位四元数 w=1
    opacity = np.full((n, 1), opacity_log, dtype=np.float32)

    dtype = [
        ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
        ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
        ('f_dc_0', 'f4'), ('f_dc_1', 'f4'), ('f_dc_2', 'f4'),
        ('opacity', 'f4'),
        ('scale_0', 'f4'), ('scale_1', 'f4'), ('scale_2', 'f4'),
        ('rot_0', 'f4'), ('rot_1', 'f4'), ('rot_2', 'f4'), ('rot_3', 'f4')
    ]

    elements = np.empty(n, dtype=dtype)
    elements['x'] = xyz[:, 0]
    elements['y'] = xyz[:, 1]
    elements['z'] = xyz[:, 2]
    elements['nx'] = 0
    elements['ny'] = 0
    elements['nz'] = 0
    elements['f_dc_0'] = f_dc[:, 0]
    elements['f_dc_1'] = f_dc[:, 1]
    elements['f_dc_2'] = f_dc[:, 2]
    elements['opacity'] = opacity[:, 0]
    elements['scale_0'] = scale[:, 0]
    elements['scale_1'] = scale[:, 1]
    elements['scale_2'] = scale[:, 2]
    elements['rot_0'] = rot[:, 0]
    elements['rot_1'] = rot[:, 1]
    elements['rot_2'] = rot[:, 2]
    elements['rot_3'] = rot[:, 3]

    PlyData([PlyElement.describe(elements, 'vertex')]).write(output_path)
    print(f"Saved {n} points → {output_path}")


def create_textured_cube_splat(output_path="scene_textured_cube.ply",
                                num_points=20000, perturb=0.05, freq=4):
    """带正弦表面纹理的立方体。扰动沿面法线方向，给 ControlNet 提供更多几何特征。"""
    print(f"Generating TEXTURED cube (2x2x2) with {num_points} surface points...")
    print(f"  Perturb amplitude={perturb}, frequency={freq}")

    points_per_face = num_points // 6
    remainder = num_points % 6

    faces = []
    for face_idx in range(6):
        n = points_per_face + (1 if face_idx < remainder else 0)
        u = np.random.rand(n) * 2 - 1  # [-1, 1]
        v = np.random.rand(n) * 2 - 1
        ones = np.ones(n)

        # 正弦扰动: sin(freq*pi*u) * cos(freq*pi*v) 沿法线偏移
        wave = perturb * np.sin(freq * np.pi * u) * np.cos(freq * np.pi * v)

        if face_idx == 0:   # +Z
            pts = np.column_stack([u, v, ones + wave])
        elif face_idx == 1: # -Z
            pts = np.column_stack([u, v, -ones + wave])
        elif face_idx == 2: # +X
            pts = np.column_stack([ones + wave, u, v])
        elif face_idx == 3: # -X
            pts = np.column_stack([-ones + wave, u, v])
        elif face_idx == 4: # +Y
            pts = np.column_stack([u, ones + wave, v])
        else:               # -Y
            pts = np.column_stack([u, -ones + wave, v])
        faces.append(pts)

    xyz = np.concatenate(faces, axis=0).astype(np.float32)
    np.random.shuffle(xyz)

    _write_ply(xyz, scale_log=-2.0, opacity_log=15.0, output_path=output_path)


def create_complex_scene(output_path="scene_complex.ply", num_points=30000):
    """多物体纹理场景: 5 个不同尺寸/纹理的立方体，分散在 [-5,5]^3。"""
    print(f"Generating COMPLEX scene with {num_points} points...")

    objects = [
        # (center_x, center_y, center_z, half_size, points, perturb, freq)
        (0.0, 0.0, 0.0,   1.2, 8000,  0.06, 5),   # 中心立方体
        (2.0, 1.0, -1.0,  0.7, 6000,  0.04, 3),   # 右前小立方体
        (-1.8, -0.8, 1.5, 0.6, 6000,  0.05, 6),   # 左后小立方体
        (1.2, -1.5, 1.8,  0.5, 5000,  0.07, 4),   # 下方小立方体
        (-1.5, 1.2, -1.5, 0.9, 5000,  0.03, 2),   # 左上扁长方体
    ]

    parts = []
    for cx, cy, cz, half, count, perturb, freq in objects:
        per_face = count // 6
        rem = count % 6
        for fi in range(6):
            n = per_face + (1 if fi < rem else 0)
            u = np.random.rand(n) * 2 - 1
            v = np.random.rand(n) * 2 - 1
            wave = perturb * np.sin(freq * np.pi * u) * np.cos(freq * np.pi * v)
            ones_u = u * half
            ones_v = v * half
            ones_h = np.ones(n) * half
            if fi == 0:
                pts = np.column_stack([ones_u + cx, ones_v + cy, ones_h + wave + cz])
            elif fi == 1:
                pts = np.column_stack([ones_u + cx, ones_v + cy, -ones_h + wave + cz])
            elif fi == 2:
                pts = np.column_stack([ones_h + wave + cx, ones_u + cy, ones_v + cz])
            elif fi == 3:
                pts = np.column_stack([-ones_h + wave + cx, ones_u + cy, ones_v + cz])
            elif fi == 4:
                pts = np.column_stack([ones_u + cx, ones_h + wave + cy, ones_v + cz])
            else:
                pts = np.column_stack([ones_u + cx, -ones_h + wave + cy, ones_v + cz])
            parts.append(pts)

    xyz = np.concatenate(parts, axis=0).astype(np.float32)
    np.random.shuffle(xyz)

    _write_ply(xyz, scale_log=-2.2, opacity_log=14.0, output_path=output_path)


# ═══════════════════════════════════════════════════════════
# 5 主题场景 PLY 生成器
# ═══════════════════════════════════════════════════════════

def _sample_cube_surface_ex(cx, cy, cz, sx, sy, sz, n_points):
    """Generate surface points for an axis-aligned box (arbitrary half-extents)."""
    per_face = n_points // 6
    rem = n_points % 6
    parts = []
    for fi in range(6):
        n = per_face + (1 if fi < rem else 0)
        u = np.random.rand(n) * 2 - 1
        v = np.random.rand(n) * 2 - 1
        if fi == 0:   pts = np.column_stack([u*sx + cx, v*sy + cy, np.full(n, sz) + cz])
        elif fi == 1: pts = np.column_stack([u*sx + cx, v*sy + cy, np.full(n, -sz) + cz])
        elif fi == 2: pts = np.column_stack([np.full(n, sx) + cx, u*sy + cy, v*sz + cz])
        elif fi == 3: pts = np.column_stack([np.full(n, -sx) + cx, u*sy + cy, v*sz + cz])
        elif fi == 4: pts = np.column_stack([u*sx + cx, np.full(n, sy) + cy, v*sz + cz])
        else:         pts = np.column_stack([u*sx + cx, np.full(n, -sy) + cy, v*sz + cz])
        parts.append(pts)
    return np.concatenate(parts, axis=0).astype(np.float32)


def _sample_cylinder(cx, cy, cz, radius, height, n_points):
    theta = np.random.uniform(0, 2*np.pi, n_points)
    h = np.random.uniform(0, height, n_points)
    return np.column_stack([cx + radius*np.cos(theta), cy + radius*np.sin(theta), cz + h]).astype(np.float32)


def _sample_sphere(cx, cy, cz, radius, n_points):
    pts = np.random.randn(n_points, 3).astype(np.float32)
    pts = pts / np.linalg.norm(pts, axis=1, keepdims=True) * radius
    pts[:, 0] += cx; pts[:, 1] += cy; pts[:, 2] += cz
    return pts


def _sample_cone(cx, cy, cz, r_bottom, r_top, height, n_points):
    t = np.random.uniform(0, 1, n_points)
    theta = np.random.uniform(0, 2*np.pi, n_points)
    r = r_bottom*(1-t) + r_top*t
    return np.column_stack([cx + r*np.cos(theta), cy + r*np.sin(theta), cz + t*height]).astype(np.float32)


def create_zen_garden_ply(output_path="scene_zen_garden.ply", num_points=40000):
    print(f"Building ZEN GARDEN PLY ({num_points} points)...")
    parts = []
    pp = num_points // 30
    # Ground
    gx = np.random.uniform(-6, 6, pp*3); gy = np.random.uniform(-5, 5, pp*3)
    parts.append(np.column_stack([gx, gy, np.zeros(pp*3)]).astype(np.float32))
    # Rocks
    for _ in range(8):
        parts.append(_sample_sphere(np.random.uniform(-4,4), np.random.uniform(-3,3), np.random.uniform(0.1,0.3), np.random.uniform(0.2,0.6), pp))
    # Trees
    for _ in range(5):
        tx, ty = np.random.uniform(-5,5), np.random.uniform(-4,4)
        parts.append(_sample_cylinder(tx, ty, 0, 0.1, 2.0, pp))
        parts.append(_sample_cone(tx, ty, 2.0, 0.8, 0.05, 1.5, pp))
    # Pond
    pr = np.sqrt(np.random.uniform(0, 1.5**2, pp))
    pa = np.random.uniform(0, 2*np.pi, pp)
    parts.append(np.column_stack([1.5+pr*np.cos(pa), -1.5+pr*np.sin(pa), np.full(pp, 0.02)]).astype(np.float32))
    # Bridge
    parts.append(_sample_cube_surface_ex(1.5, -1.5, 0.15, 0.3, 2.0, 0.08, pp))
    # Path stones
    for i in range(8):
        parts.append(_sample_cylinder(-2+i*0.5, 0.5+np.sin(i)*0.3, 0.02, 0.15, 0.03, pp//2))

    xyz = np.concatenate(parts, axis=0).astype(np.float32)[:num_points]
    np.random.shuffle(xyz)
    _write_ply(xyz, scale_log=-2.0, opacity_log=14.0, output_path=output_path)


def create_scifi_corridor_ply(output_path="scene_scifi_corridor.ply", num_points=40000):
    print(f"Building SCIFI CORRIDOR PLY ({num_points} points)...")
    parts = []; L = 8; pp = num_points // 25
    # Floor + Ceiling
    parts.append(_sample_cube_surface_ex(0, 0, -1.8, 2.5, L, 0.1, pp))
    parts.append(_sample_cube_surface_ex(0, 0, 2.5, 2.5, L, 0.1, pp))
    # Walls
    parts.append(_sample_cube_surface_ex(-2.5, 0, 0.3, 0.1, L, 2.5, pp))
    parts.append(_sample_cube_surface_ex(2.5, 0, 0.3, 0.1, L, 2.5, pp))
    # Pillars
    for i in range(8):
        for sx in [-1.8, 1.8]:
            parts.append(_sample_cylinder(sx, -6+i*1.5, -0.8, 0.12, 3.5, pp//2))
    # Floor ridges
    for i in range(20):
        parts.append(_sample_cube_surface_ex(0, -7+i*0.7, -1.7, 2.0, 0.03, 0.03, pp//3))
    # End wall
    parts.append(_sample_cube_surface_ex(0, -7, 0.3, 2.5, 0.1, 2.5, pp))

    xyz = np.concatenate(parts, axis=0).astype(np.float32)[:num_points]
    np.random.shuffle(xyz)
    _write_ply(xyz, scale_log=-2.2, opacity_log=14.0, output_path=output_path)


def create_floating_islands_ply(output_path="scene_floating_islands.ply", num_points=40000):
    print(f"Building FLOATING ISLANDS PLY ({num_points} points)...")
    parts = []
    islands = [(0,0,4,3.0), (5,-2,3,2.0), (-4,1,5,2.5), (3,4,2,1.5), (-3,-3,3.5,1.8)]
    pp = num_points // (len(islands)*3)
    for cx, cy, cz, size in islands:
        parts.append(_sample_cylinder(cx, cy, cz, size, 0.3, pp))
        parts.append(_sample_cone(cx, cy, cz-2.0, size*0.8, size*0.3, 2.0, pp))
    # Crystals
    for _ in range(15):
        idx = np.random.randint(0, len(islands))
        ix = islands[idx][0] + np.random.uniform(-0.5, 0.5)
        iy = islands[idx][1] + np.random.uniform(-0.5, 0.5)
        iz = islands[idx][2] + 0.3 + np.random.uniform(0, 0.8)
        parts.append(_sample_cone(ix, iy, iz, 0.08, 0.01, np.random.uniform(0.3, 1.5), pp//2))

    xyz = np.concatenate(parts, axis=0).astype(np.float32)[:num_points]
    np.random.shuffle(xyz)
    _write_ply(xyz, scale_log=-2.0, opacity_log=14.0, output_path=output_path)


def create_desert_ruins_ply(output_path="scene_desert_ruins.ply", num_points=40000):
    print(f"Building DESERT RUINS PLY ({num_points} points)...")
    parts = []; pp = num_points // 20
    # Sandy ground
    gx = np.random.uniform(-8, 8, pp*3); gy = np.random.uniform(-8, 8, pp*3)
    gz = np.random.uniform(-0.1, 0.1, pp*3) + 0.05*np.sin(gx*0.5)*np.cos(gy*0.5)
    parts.append(np.column_stack([gx, gy, gz]).astype(np.float32))
    # Pyramid
    parts.append(_sample_cone(0, 0, 2, 3, 0.05, 4, pp*2))
    # Columns
    for i in range(8):
        a = i*np.pi/4; r = 4.5
        parts.append(_sample_cylinder(r*np.cos(a), r*np.sin(a), 0, 0.25, 3, pp))
    # Obelisks
    for i in range(4):
        a = i*np.pi/2 + np.pi/6; r = 6
        parts.append(_sample_cube_surface_ex(r*np.cos(a), r*np.sin(a), 1.2, 0.2, 0.2, 2.0, pp))

    xyz = np.concatenate(parts, axis=0).astype(np.float32)[:num_points]
    np.random.shuffle(xyz)
    _write_ply(xyz, scale_log=-2.0, opacity_log=14.0, output_path=output_path)


def create_forest_glade_ply(output_path="scene_forest_glade.ply", num_points=50000):
    print(f"Building FOREST GLADE PLY ({num_points} points)...")
    parts = []; pp = num_points // 30
    # Ground
    gx = np.random.uniform(-8, 8, pp*3); gy = np.random.uniform(-8, 8, pp*3)
    parts.append(np.column_stack([gx, gy, np.random.uniform(0, 0.05, pp*3)]).astype(np.float32))
    # Trees
    for _ in range(15):
        tx = np.random.uniform(-6, 6); ty = np.random.uniform(-6, 6)
        if abs(tx) < 1.5 and abs(ty) < 1.5:
            tx = np.random.choice([np.random.uniform(-6,-2), np.random.uniform(2,6)])
        h = np.random.uniform(1.5, 3.5); r = np.random.uniform(0.06, 0.18)
        parts.append(_sample_cylinder(tx, ty, 0, r, h, pp))
        for _ in range(np.random.randint(2, 4)):
            parts.append(_sample_cone(tx, ty, h*0.6, np.random.uniform(0.5,1.0), 0.02, np.random.uniform(0.6,1.2), pp))
    # Stone circle
    for i in range(12):
        a = i*np.pi/6; r = 1.8
        parts.append(_sample_cylinder(r*np.cos(a), r*np.sin(a), 0.02, 0.12, np.random.uniform(0.3,0.8), pp//2))

    xyz = np.concatenate(parts, axis=0).astype(np.float32)[:num_points]
    np.random.shuffle(xyz)
    _write_ply(xyz, scale_log=-2.0, opacity_log=14.0, output_path=output_path)


if __name__ == "__main__":
    print("=" * 50)
    print("  Generating all CineAnchor scene PLYs")
    print("=" * 50)
    create_cube_splat("test_scene.ply", num_points=20000)
    create_large_cube_splat("scene_large_cube.ply", num_points=30000)
    create_multi_object_splat("scene_multi.ply", num_points=30000)
    create_textured_cube_splat("scene_textured_cube.ply", num_points=20000)
    create_complex_scene("scene_complex.ply", num_points=30000)
    create_zen_garden_ply("scene_zen_garden.ply")
    create_scifi_corridor_ply("scene_scifi_corridor.ply")
    create_floating_islands_ply("scene_floating_islands.ply")
    create_desert_ruins_ply("scene_desert_ruins.ply")
    create_forest_glade_ply("scene_forest_glade.ply")
    print("\nDone. 10 PLY files generated.")
