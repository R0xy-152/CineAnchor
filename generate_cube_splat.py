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


if __name__ == "__main__":
    print("=" * 50)
    print("  Generating all CineAnchor scene PLYs")
    print("=" * 50)
    create_cube_splat("test_scene.ply", num_points=20000)
    create_large_cube_splat("scene_large_cube.ply", num_points=30000)
    create_multi_object_splat("scene_multi.ply", num_points=30000)
    create_textured_cube_splat("scene_textured_cube.ply", num_points=20000)
    create_complex_scene("scene_complex.ply", num_points=30000)
    print("\nDone. 5 PLY files generated.")
