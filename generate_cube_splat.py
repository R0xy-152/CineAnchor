import numpy as np
from plyfile import PlyData, PlyElement
import os

def create_cube_splat(output_path="test_scene.ply", num_points=20000):
    print(f"Generating procedural 3DGS cube with {num_points} points...")
    
    # 1. 随机生成位于 -1 到 1 之间的立方体坐标
    xyz = (np.random.rand(num_points, 3) * 2 - 1).astype(np.float32)
    
    # 2. 根据坐标位置赋予颜色 (XYZ 映射到 RGB)
    # 左下角是黑色，右上角是白色，产生绚丽的渐变色
    rgb = (xyz + 1) / 2.0 
    
    # 将 RGB 转换为球谐函数 (SH) 的第一项直流分量 (DC)
    # 3DGS 公式：SH_C0 = 0.28209479177387814
    # color = SH_DC * SH_C0 + 0.5  =>  SH_DC = (color - 0.5) / SH_C0
    C0 = 0.28209479177387814
    f_dc = ((rgb - 0.5) / C0).astype(np.float32)
    
    # 3. 缩放参数 (非常小的高斯球，形成密集的表面)
    # 3DGS 中 scale 是指数存储的，-4 左右代表非常小的点
    scale = np.full((num_points, 3), -4.0, dtype=np.float32)
    
    # 4. 旋转参数 (四元数 w, x, y, z)
    # 使用单位四元数 [1, 0, 0, 0] 表示无旋转
    rot = np.zeros((num_points, 4), dtype=np.float32)
    rot[:, 0] = 1.0 
    
    # 5. 不透明度 (Inverse Sigmoid 空间)
    # 传入很大的值代表接近 1.0 (完全不透明)
    opacity = np.full((num_points, 1), 10.0, dtype=np.float32)
    
    # 组装顶点数据
    dtype = [
        ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
        ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
        ('f_dc_0', 'f4'), ('f_dc_1', 'f4'), ('f_dc_2', 'f4'),
        ('opacity', 'f4'),
        ('scale_0', 'f4'), ('scale_1', 'f4'), ('scale_2', 'f4'),
        ('rot_0', 'f4'), ('rot_1', 'f4'), ('rot_2', 'f4'), ('rot_3', 'f4')
    ]
    
    elements = np.empty(num_points, dtype=dtype)
    elements['x'] = xyz[:, 0]
    elements['y'] = xyz[:, 1]
    elements['z'] = xyz[:, 2]
    # 法线全置 0
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
    
    # 保存为 PLY 文件
    el = PlyElement.describe(elements, 'vertex')
    PlyData([el]).write(output_path)
    print(f"Successfully saved to {output_path}")

if __name__ == "__main__":
    create_cube_splat()
