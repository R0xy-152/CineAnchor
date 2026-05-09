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


if __name__ == "__main__":
    create_cube_splat()
