import torch
import numpy as np
from PIL import Image
import os
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel
import cv2


class ControlNetRenderer:
    """
    ControlNet-Depth 渲染器：将深度图作为条件输入，使用 Stable Diffusion 生成 RGB 图像。

    两种批量模式：
    - render_batch(): 逐帧独立生成 (当前)
    - render_animated(): AnimateDiff 时序注意力 (新增，帧间一致)
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

        self.base_model_id = base_model_id
        self._animatediff_loaded = False
        print("ControlNet pipeline loaded successfully.")

    def render_rgb(self, depth_map_path: str, prompt: str, output_path: str,
                   num_inference_steps: int = 20, guidance_scale: float = 7.5,
                   seed: int = 42,
                   controlnet_conditioning_scale: float = 1.0) -> str:
        """
        从深度图生成 RGB 图像。

        Args:
            depth_map_path: 输入深度图路径 (PNG)
            prompt: Stable Diffusion prompt
            output_path: 输出 RGB 图像路径 (PNG)
            num_inference_steps: 推理步数
            guidance_scale: CFG scale
            seed: 随机种子
            controlnet_conditioning_scale: ControlNet 对 UNet 的注入强度。
                0.7-0.85 = 平衡几何约束与纹理自由度，推荐用于视频序列
                1.0      = 严格跟随深度 (默认)，深度不一致时可能加剧扭曲

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
                controlnet_conditioning_scale=controlnet_conditioning_scale,
                generator=generator,
            )

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        output.images[0].save(output_path)
        print(f"RGB image saved to: {output_path}")

        return output_path

    def render_batch(self, depth_dir: str, prompt: str, output_dir: str,
                     num_inference_steps: int = 20, seed: int = 42,
                     controlnet_conditioning_scale: float = 1.0) -> list[str]:
        """
        批量渲染：读取目录下所有深度图，逐帧生成 RGB 图像。

        Args:
            depth_dir: 输入深度图目录
            prompt: Stable Diffusion prompt
            output_dir: 输出目录
            num_inference_steps: 推理步数
            seed: 随机种子 (所有帧共用，确保噪声模式一致)
            controlnet_conditioning_scale: ControlNet 注入强度。1.0=严格跟随深度 (推荐)

        Returns:
            输出文件路径列表
        """
        depth_files = sorted(
            f for f in os.listdir(depth_dir) if f.endswith('.png')
        )
        if not depth_files:
            raise FileNotFoundError(f"No PNG files found in {depth_dir}")

        print(f"Found {len(depth_files)} depth maps in {depth_dir}")
        print(f"Seed: {seed} (unified), "
              f"conditioning_scale={controlnet_conditioning_scale}")
        os.makedirs(output_dir, exist_ok=True)

        output_paths = []
        for i, filename in enumerate(depth_files):
            depth_path = os.path.join(depth_dir, filename)
            output_name = f"rgb_frame_{i:04d}.png"
            output_path = os.path.join(output_dir, output_name)

            print(f"[{i+1}/{len(depth_files)}] {filename} → {output_name}")
            self.render_rgb(depth_path, prompt, output_path,
                            num_inference_steps=num_inference_steps,
                            seed=seed,
                            controlnet_conditioning_scale=controlnet_conditioning_scale)
            output_paths.append(output_path)

        print(f"Batch render complete: {len(output_paths)} frames → {output_dir}")
        return output_paths


    # ---- AnimateDiff 时序注意力 (所有帧在一个扩散过程中生成) ----

    def _load_animatediff(self):
        """加载 AnimateDiff motion adapter 和时序管线 (首次调用时)"""
        if self._animatediff_loaded:
            return

        from diffusers import AnimateDiffControlNetPipeline, MotionAdapter
        from diffusers.schedulers import DDIMScheduler

        print("Loading AnimateDiff motion adapter...")
        motion_adapter = MotionAdapter.from_pretrained(
            "guoyww/animatediff-motion-adapter-v1-5-2",
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
        )

        print("Building AnimateDiffControlNetPipeline...")
        self.animate_pipe = AnimateDiffControlNetPipeline.from_pretrained(
            self.base_model_id,
            controlnet=self.controlnet,
            motion_adapter=motion_adapter,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
            safety_checker=None,
        )

        # 用 DDIM scheduler (AnimateDiff 推荐)
        self.animate_pipe.scheduler = DDIMScheduler.from_config(
            self.animate_pipe.scheduler.config
        )

        if self.device.type == "cuda":
            self.animate_pipe.enable_model_cpu_offload()

        self._animatediff_loaded = True
        print("AnimateDiff pipeline ready.")

    def render_animated(self, depth_paths: list[str], prompt: str,
                        output_dir: str,
                        num_inference_steps: int = 25,
                        guidance_scale: float = 7.5,
                        seed: int = 42,
                        controlnet_conditioning_scale: float = 1.0) -> list[str]:
        """
        AnimateDiff + ControlNet 联合生成。
        所有帧在一个扩散过程中同时生成，每帧之间共享时序注意力层，
        从根源消除帧间纹理漂移。

        Args:
            depth_paths: 深度图路径列表 (按时间顺序)
            prompt: Stable Diffusion prompt
            output_dir: 输出目录
            num_inference_steps: 推理步数 (推荐 25)
            guidance_scale: CFG scale
            seed: 随机种子
            controlnet_conditioning_scale: ControlNet 注入强度

        Returns:
            输出 RGB 帧路径列表
        """
        if len(depth_paths) < 2:
            return self._fallback_batch(depth_paths, prompt, output_dir, seed,
                                        controlnet_conditioning_scale)

        self._load_animatediff()

        # 加载并预处理所有深度图
        depth_images = []
        for p in depth_paths:
            img = Image.open(p).convert("RGB")
            if img.size != (512, 512):
                img = img.resize((512, 512), Image.LANCZOS)
            depth_images.append(img)

        print(f"AnimateDiff render: {len(depth_images)} frames, "
              f"{num_inference_steps} steps, seed={seed}")

        negative = ("bad quality, blurry, distorted, warped, jitter, "
                    "inconsistent, flickering")

        generator = torch.Generator(device=self.device).manual_seed(seed)

        with torch.inference_mode():
            output = self.animate_pipe(
                prompt=prompt,
                negative_prompt=negative,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                controlnet_conditioning_scale=controlnet_conditioning_scale,
                conditioning_frames=depth_images,
                num_frames=len(depth_images),
                width=512,
                height=512,
                generator=generator,
            )

        os.makedirs(output_dir, exist_ok=True)
        output_paths = []
        for i, frame in enumerate(output.frames[0]):
            out = os.path.join(output_dir, f"rgb_frame_{i:04d}.png")
            frame.save(out)
            output_paths.append(out)

        print(f"AnimateDiff complete: {len(output_paths)} frames → {output_dir}")
        return output_paths

    def _fallback_batch(self, depth_paths, prompt, output_dir, seed,
                        conditioning_scale):
        """单帧或无 AnimateDiff 时的降级: 逐帧独立渲染"""
        print("[AnimateDiff] < 2 frames, falling back to independent render")
        paths = []
        for i, dp in enumerate(depth_paths):
            out = os.path.join(output_dir, f"rgb_frame_{i:04d}.png")
            self.render_rgb(dp, prompt, out, seed=seed,
                            controlnet_conditioning_scale=conditioning_scale)
            paths.append(out)
        return paths


if __name__ == "__main__":
    renderer = ControlNetRenderer()

    prompt = "a colorful cube floating in dark space, studio lighting, high quality"

    # 单帧测试
    renderer.render_rgb(
        "real_depth_maps/test_scene_real_depth_frame_0000.png",
        prompt,
        "controlnet_output/test_scene_rgb_0000.png",
    )

    # 批量渲染 (独立帧)
    renderer.render_batch(
        "real_depth_maps/",
        prompt,
        "controlnet_output/frames/",
    )
