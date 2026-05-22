import torch
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import os
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel
import cv2


class ControlNetRenderer:
    """
    ControlNet-Depth 渲染器：将深度图作为条件输入，使用 Stable Diffusion 生成 RGB 图像。

    SD 1.5 模式 (默认):
    - render_batch(): 逐帧独立生成
    - render_animated(): AnimateDiff 时序注意力

    SDXL 模式 (use_sdxl=True):
    - render_batch(): 逐帧独立生成 (768×768)
    - render_animated(): 降级到逐帧 (无 AnimateDiff SDXL 支持)
    - 使用 controlnet-depth-sdxl-1.0-small (~320MB) 节省 VRAM
    """

    def __init__(self, controlnet_id="lllyasviel/control_v11f1p_sd15_depth",
                 base_model_id="runwayml/stable-diffusion-v1-5",
                 use_sdxl: bool = False,
                 sdxl_resolution: int = 768,
                 sd15_resolution: int = 576):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.use_sdxl = use_sdxl
        self.target_size = sdxl_resolution if use_sdxl else sd15_resolution

        if use_sdxl:
            controlnet_id = "diffusers/controlnet-depth-sdxl-1.0-small"
            base_model_id = "stabilityai/stable-diffusion-xl-base-1.0"

        print(f"Initializing ControlNetRenderer on device: {self.device}")
        print(f"  Mode: {'SDXL' if use_sdxl else 'SD 1.5'}, "
              f"target: {self.target_size}×{self.target_size}")

        print(f"Loading ControlNet: {controlnet_id} ...")
        self.controlnet = ControlNetModel.from_pretrained(
            controlnet_id,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
        )

        print(f"Loading base SD model: {base_model_id} ...")

        if use_sdxl:
            from diffusers import StableDiffusionXLControlNetPipeline
            self.pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
                base_model_id,
                controlnet=self.controlnet,
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
            )
        else:
            self.pipe = StableDiffusionControlNetPipeline.from_pretrained(
                base_model_id,
                controlnet=self.controlnet,
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
                safety_checker=None,
            )

        if self.device.type == "cuda":
            self.pipe = self.pipe.to(self.device)
            self.pipe.enable_model_cpu_offload()
            self.pipe.enable_vae_slicing()
            self.pipe.enable_vae_tiling()

        self.base_model_id = base_model_id
        self._animatediff_loaded = False
        print("ControlNet pipeline loaded successfully.")

    def _enhance_depth(self, depth_image):
        """Canny 边缘叠加到深度图，给 ControlNet 更强的几何特征"""
        import cv2
        gray = cv2.cvtColor(np.array(depth_image), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        # 边缘处提亮，非边缘处略微压暗 → 提升几何对比度
        enhanced = gray.astype(np.float32)
        enhanced = enhanced * 0.9 + edges.astype(np.float32) * 0.3
        enhanced = np.clip(enhanced, 0, 255).astype(np.uint8)
        return Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB))

    def _polish_frame(self, image: Image.Image) -> Image.Image:
        """轻量后处理，让预览帧更清晰，但不改变构图。"""
        image = ImageEnhance.Contrast(image).enhance(1.08)
        image = ImageEnhance.Sharpness(image).enhance(1.25)
        return image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=70, threshold=3))

    def render_rgb(self, depth_map_path: str, prompt: str, output_path: str,
                   num_inference_steps: int = 20, guidance_scale: float = 7.5,
                   seed: int = 42,
                   controlnet_conditioning_scale: float = 1.0,
                   enhance_depth: bool = False) -> str:
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

        ts = (self.target_size, self.target_size)
        if depth_image.size != ts:
            depth_image = depth_image.resize(ts, Image.LANCZOS)

        if enhance_depth:
            depth_image = self._enhance_depth(depth_image)

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
        self._polish_frame(output.images[0]).save(output_path)
        print(f"RGB image saved to: {output_path}")

        return output_path

    def render_batch(self, depth_dir: str, prompt: str, output_dir: str,
                     num_inference_steps: int = 20, seed: int = 42,
                     controlnet_conditioning_scale: float = 1.0,
                     enhance_depth: bool = False) -> list[str]:
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
                            controlnet_conditioning_scale=controlnet_conditioning_scale,
                            enhance_depth=enhance_depth)
            output_paths.append(output_path)

        print(f"Batch render complete: {len(output_paths)} frames → {output_dir}")
        return output_paths


    # ---- AnimateDiff 时序注意力 (所有帧在一个扩散过程中生成) ----

    def _load_animatediff(self):
        """加载 AnimateDiff motion adapter 和时序管线 (首次调用时)"""
        if self.use_sdxl:
            raise RuntimeError(
                "AnimateDiff not available in SDXL mode. "
                "Use render_batch() for per-frame rendering."
            )
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
            # sequential offload: 同一时刻只有活跃子模型在 GPU，其余在 CPU
            # CPU 内存就是 Windows 共享 GPU 内存 → 充分利用空闲共享内存
            self.animate_pipe.enable_sequential_cpu_offload()
            self.animate_pipe.enable_vae_slicing()   # VAE 分批解码，降峰值
            self.animate_pipe.enable_vae_tiling()    # VAE 分块处理大图
            self.animate_pipe.enable_attention_slicing()  # 注意力分片

        self._animatediff_loaded = True
        print("AnimateDiff pipeline ready (sequential offload + vae/attention slicing).")

    def render_animated(self, depth_paths: list[str], prompt: str,
                        output_dir: str,
                        num_inference_steps: int = 25,
                        guidance_scale: float = 7.5,
                        seed: int = 42,
                        controlnet_conditioning_scale: float = 1.0,
                        enhance_depth: bool = False,
                        max_frames: int = 16) -> list[str]:
        """
        AnimateDiff + ControlNet 联合生成。

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

        # SDXL 模式: 无 AnimateDiff，降级逐帧渲染
        if self.use_sdxl:
            print("[SDXL] AnimateDiff not available, rendering per-frame")
            return self._fallback_batch(depth_paths, prompt, output_dir, seed,
                                        controlnet_conditioning_scale)

        self._load_animatediff()

        if len(depth_paths) > max_frames:
            sample_idx = np.linspace(0, len(depth_paths) - 1, max_frames).round().astype(int)
            depth_paths = [depth_paths[i] for i in sample_idx]
            print(f"AnimateDiff frame budget: sampled {len(depth_paths)} frames from source sequence")

        # 加载并预处理所有深度图
        depth_images = []
        for p in depth_paths:
            img = Image.open(p).convert("RGB")
            ts = (self.target_size, self.target_size)
            if img.size != ts:
                img = img.resize(ts, Image.LANCZOS)
            if enhance_depth:
                img = self._enhance_depth(img)
            depth_images.append(img)

        print(f"AnimateDiff render: {len(depth_images)} frames, "
              f"{num_inference_steps} steps, seed={seed}")

        negative = ("blurry, soft edges, rounded shape, sphere, organic, "
                    "warped, distorted, jitter, flickering, inconsistent, "
                    "low contrast, flat shading, foggy, haze")

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
                width=self.target_size,
                height=self.target_size,
                generator=generator,
            )

        os.makedirs(output_dir, exist_ok=True)
        output_paths = []
        for i, frame in enumerate(output.frames[0]):
            out = os.path.join(output_dir, f"rgb_frame_{i:04d}.png")
            self._polish_frame(frame).save(out)
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
