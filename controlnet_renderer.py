import torch
import numpy as np
from PIL import Image
import os
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel
from controlnet_aux import CannyDetector
import cv2


class ControlNetRenderer:
    """
    ControlNet-Depth 渲染器：将深度图作为条件输入，使用 Stable Diffusion 生成 RGB 图像。
    """

    def __init__(self, controlnet_id="lllyasviel/control_v11f1p_sd15_depth",
                 base_model_id="runwayml/stable-diffusion-v1-5"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Initializing ControlNetRenderer on device: {self.device}")

        print(f"Loading ControlNet: {controlnet_id} ...")
        self.controlnet = ControlNetModel.from_pretrained(
            controlnet_id,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
        )

        print(f"Loading base SD model: {base_model_id} ...")
        self.pipe = StableDiffusionControlNetPipeline.from_pretrained(
            base_model_id,
            controlnet=self.controlnet,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
            safety_checker=None,
        )

        if self.device.type == "cuda":
            self.pipe = self.pipe.to(self.device)
            self.pipe.enable_model_cpu_offload()  # 节省 VRAM

        print("ControlNet pipeline loaded successfully.")

    def render_rgb(self, depth_map_path: str, prompt: str, output_path: str,
                   num_inference_steps: int = 20, guidance_scale: float = 7.5,
                   seed: int = 42) -> str:
        """
        从深度图生成 RGB 图像。

        Args:
            depth_map_path: 输入深度图路径 (PNG)
            prompt: Stable Diffusion prompt
            output_path: 输出 RGB 图像路径 (PNG)
            num_inference_steps: 推理步数
            guidance_scale: CFG scale
            seed: 随机种子

        Returns:
            输出文件路径
        """
        depth_image = Image.open(depth_map_path).convert("RGB")
        print(f"Input depth map size: {depth_image.size}")

        # 调整到 SD 1.5 期望的 512 分辨率
        if depth_image.size != (512, 512):
            depth_image = depth_image.resize((512, 512), Image.LANCZOS)

        generator = torch.Generator(device=self.device).manual_seed(seed)

        with torch.inference_mode():
            output = self.pipe(
                prompt=prompt,
                image=depth_image,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
            )

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        output.images[0].save(output_path)
        print(f"RGB image saved to: {output_path}")

        return output_path

    def render_batch(self, depth_dir: str, prompt: str, output_dir: str,
                     num_inference_steps: int = 20, seed: int = 42) -> list[str]:
        """
        批量渲染：读取目录下所有深度图，逐帧生成 RGB 图像。

        Args:
            depth_dir: 输入深度图目录
            prompt: Stable Diffusion prompt
            output_dir: 输出目录
            num_inference_steps: 推理步数
            seed: 随机种子

        Returns:
            输出文件路径列表
        """
        depth_files = sorted(
            f for f in os.listdir(depth_dir) if f.endswith('.png')
        )
        if not depth_files:
            raise FileNotFoundError(f"No PNG files found in {depth_dir}")

        print(f"Found {len(depth_files)} depth maps in {depth_dir}")
        os.makedirs(output_dir, exist_ok=True)

        output_paths = []
        for i, filename in enumerate(depth_files):
            depth_path = os.path.join(depth_dir, filename)
            output_name = f"rgb_frame_{i:04d}.png"
            output_path = os.path.join(output_dir, output_name)

            print(f"[{i+1}/{len(depth_files)}] {filename} → {output_name}")
            self.render_rgb(depth_path, prompt, output_path,
                            num_inference_steps=num_inference_steps, seed=seed)
            output_paths.append(output_path)

        print(f"Batch render complete: {len(output_paths)} frames → {output_dir}")
        return output_paths


if __name__ == "__main__":
    renderer = ControlNetRenderer()

    prompt = "a colorful cube floating in dark space, studio lighting, high quality"

    # 单帧测试
    renderer.render_rgb(
        "real_depth_maps/test_scene_real_depth_frame_0000.png",
        prompt,
        "controlnet_output/test_scene_rgb_0000.png",
    )

    # 批量渲染
    renderer.render_batch(
        "real_depth_maps/",
        prompt,
        "controlnet_output/frames/",
    )
