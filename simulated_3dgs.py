import numpy as np
import os
from PIL import Image

class Simulated3DGS:
    def __init__(self):
        # 预设几个模拟场景
        self.scenes = {
            "office_scene": {
                "description": "一个有桌椅的简单办公室，窗外是城市景观。",
                "depth_map_template": self._generate_simple_depth_map(width=512, height=288, near=1.0, far=10.0)
            },
            "forest_path": {
                "description": "一条穿过茂密森林的小径，阳光从树叶间洒落。",
                "depth_map_template": self._generate_simple_depth_map(width=512, height=288, near=0.5, far=20.0, inverted=True)
            }
        }
        self.output_dir = "simulated_depth_maps"
        os.makedirs(self.output_dir, exist_ok=True)

    def _generate_simple_depth_map(self, width, height, near, far, inverted=False):
        """生成一个简单的渐变深度图作为模板"""
        depth_map = np.linspace(near, far, width * height).reshape(height, width)
        if inverted:
            depth_map = far - (depth_map - near)
        # 归一化到 0-255 用于可视化
        normalized_depth = (255 * (depth_map - np.min(depth_map)) / (np.max(depth_map) - np.min(depth_map))).astype(np.uint8)
        return normalized_depth

    def render_depth_map(self, scene_id: str, camera_pose: dict, frame_id: int, width: int = 512, height: int = 288) -> str:
        """
        模拟 3DGS 渲染深度图。
        在 MVP 阶段，我们只是基于预设模板生成一个深度图文件名。
        实际的 3DGS 渲染会根据 camera_pose 和 scene_id 生成真实的深度图。
        """
        if scene_id not in self.scenes:
            raise ValueError(f"Scene '{scene_id}' not found in simulated scenes.")

        # 模拟深度图内容（这里只是使用模板，实际会根据 camera_pose 变化）
        depth_data = self.scenes[scene_id]["depth_map_template"]

        # 构造输出路径
        filename = f"{scene_id}_depth_frame_{frame_id:04d}.png"
        filepath = os.path.join(self.output_dir, filename)

        # 保存为图片
        img = Image.fromarray(depth_data)
        img.save(filepath)

        print(f"Simulated depth map saved to: {filepath}")
        return filepath

    def get_scene_description(self, scene_id: str) -> str:
        """获取模拟场景的描述"""
        return self.scenes.get(scene_id, {}).get("description", "Unknown scene.")

# 示例用法 (仅用于测试)
if __name__ == "__main__":
    sim_3dgs = Simulated3DGS()
    camera_pose_example = {
        "position": {"x": 0.5, "y": 1.2, "z": -3.0},
        "rotation": {"x": 0.0, "y": 0.707, "z": 0.0, "w": 0.707}
    }
    
    # 渲染几帧深度图
    for i in range(3):
        sim_3dgs.render_depth_map(scene_id="office_scene", camera_pose=camera_pose_example, frame_id=i)
    
    for i in range(2):
        sim_3dgs.render_depth_map(scene_id="forest_path", camera_pose=camera_pose_example, frame_id=i)

    print(f"Office scene description: {sim_3dgs.get_scene_description('office_scene')}")
