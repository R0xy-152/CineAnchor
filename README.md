
<p align="center">
  <img src="https://img.shields.io/badge/status-MVP-green" alt="MVP Ready">
  <img src="https://img.shields.io/badge/python-3.10-blue" alt="Python 3.10">
  <img src="https://img.shields.io/badge/CUDA-12.1-green" alt="CUDA 12.1">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License">
</p>

# 🎬 CineAnchor

**3D Gaussian Splatting as Spatial Anchor for Controllable AI Video Generation.**

CineAnchor 用 3D 高斯泼溅（3DGS）将三维场景嵌入扩散模型的生成过程 —— 你在 3D 取景器中构图，AI 用 ControlNet + AnimateDiff 逐帧生成风格化视频。

> **只需一台机器即可运行。** 有 NVIDIA GPU → 完整 AI 视频生成；纯 CPU (macOS/Linux) → 模拟模式跑通全流程。

---

## 🧠 核心思路

传统 AI 视频生成（Sora, Runway）依赖文本或图像 prompt，**缺乏对三维空间结构的精确控制**。CineAnchor 的创新在于：

```
3DGS 场景 → 深度图序列 (空间锚点) → ControlNet-Depth → AnimateDiff 时序生成 → 视频
                  ↑                                              ↑
           几何一致性保证                                   运动一致性保证
```

 **3DGS = 空间锚点**：不是从噪声中幻想场景，而是从已有的三维重建中渲染精确深度  
 **深度图 = 几何约束**：ControlNet 将深度作为条件注入 SD，确保输出与场景结构对齐  
 **AnimateDiff = 时序一致**：跨帧注意力机制消除闪烁/抖动，视频稳定连贯  

---

## 🏗️ 管线架构

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  PLY 场景     │ →  │  3DGS 渲染   │ →  │  ControlNet  │ →  │  AnimateDiff │
│  (3D高斯泼溅) │    │  深度图序列   │    │  RGB 帧生成   │    │  时序注意力   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                    │
                                                                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   MP4 视频    │ ←  │ ffmpeg/OpenCV│ ←  │  RAFT 插值   │ ←  │  帧序列       │
│              │    │  视频合成     │    │  3x 平滑      │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

---

## 🎮 功能清单

### 3D 取景器
- **三相机模式**：Orbit（旋转缩放）/ Drone（WASD飞行）/ FPS（第一人称）
- **物理手感模型**：死区、加速曲线、减速阻尼，支持 Gamepad 手柄
- **3D 场景代理**：Three.js 实时预览场景布局
- **深度图实时预览**：录制时伪彩色（inferno）显示深度图
- **相机轨迹 3D 可视化**：绿色折线 + 录制点球体实时更新

### AI 渲染
- **ControlNet-Depth** (`lllyasviel/control_v11f1p_sd15_depth`)：深度图 → RGB 几何约束
- **AnimateDiff** (`guoyww/animatediff-motion-adapter-v1-5-2`)：跨帧时序注意力
- **RAFT 光流插值**：3x 帧率倍增平滑过渡
- **可调参数**：conditioning_scale / 推理步数 / seed / prompt

### 场景系统
- **3 个 SDF 场景**：立方体、办公室、森林小径（macOS 模拟渲染）
- **3DGS PLY 场景**：纹理立方体（NVIDIA GPU 渲染，ratio 1.21 最佳识别度）
- 支持自定义 PLY 文件

### 工程特性
- **自动环境检测**：启动时检测 GPU/CUDA 可用性，自动切换真实渲染 / 模拟降级
- **多级优雅降级**：GPU → CPU 模拟深度 / ffmpeg → OpenCV → 帧序列 / AnimateDiff → 逐帧
- **跨平台**：macOS/Linux（前端 + API + 模拟渲染）/ Windows（GPU 全管线）均支持

---

## 🚀 快速开始

### 硬件要求

| 模式 | 需要 | 效果 |
|------|------|------|
| **GPU 模式** | NVIDIA GPU (8GB+ VRAM, CUDA 12.1) | 真实 AI 生成画面 |
| **CPU 模式** | 任何机器 (macOS/Linux) | 模拟深度着色，体验完整工作流 |

### 安装依赖

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install diffusers transformers accelerate gsplat plyfile pillow numpy
pip install fastapi uvicorn pydantic opencv-python
```

### 启动

```bash
python3 main.py                        # 启动 API (http://localhost:8001)
open http://localhost:8001             # 打开浏览器取景器
```

### 生成视频

**方式一：前端交互** — 在取景器中选场景 → 操控相机录制帧 → 点击"生成视频"

**方式二：命令行** — 端到端一键测试（需要 GPU）:
```bash
python generate_cube_splat.py
python e2e_test.py --sd15              # SD 1.5 + AnimateDiff
```

---

## 📁 项目结构

```
CineAnchor/
├── main.py                   # FastAPI 服务器
├── static/
│   └── viewfinder.html       # 3D 取景器前端 (Three.js)
├── real_3dgs.py              # gsplat 3DGS 渲染器 (GPU)
├── controlnet_renderer.py    # ControlNet + AnimateDiff RGB 生成
├── video_renderer.py         # 渲染管线编排 + 视频合成
├── frame_interpolator.py     # RAFT 光流帧插值
├── simulated_3dgs.py         # SDF 模拟渲染 (CPU 开发)
├── generate_cube_splat.py    # PLY 场景生成器
├── e2e_test.py               # 端到端测试
└── test_api.py               # API 测试
```

---

## ⚙️ 调优结论

| 配置 | ratio (越高越好) | std (越低越好) | 结论 |
|------|:---:|:---:|------|
| SD 1.5 + AnimateDiff, scale=1.7 | **1.21** | **0.049** | ✅ 最优 |
| + Canny 边缘增强 | 1.09 | 0.087 | ❌ 反效果 |
| SDXL small ControlNet 768px | 0.53 | 0.115 | ❌ 8GB 显存不足 |

**最优配置：** SD 1.5 + AnimateDiff, conditioning_scale=1.7, seed=42, steps=25, 纹理立方体 PLY

---

## 🔮 已知限制 & 未来路线

| 限制 | 根因 | 计划 |
|------|------|------|
| ratio 天花板 1.21 | 3DGS 体渲染边缘柔化 + SD 1.5 分辨率 | SDXL 完整版 ControlNet (需 12GB+ VRAM) |
| 场景需预制 PLY | 未集成 text-to-3D 模块 | DreamGaussian / Luma API |
| macOS 无 GPU 推理 | 模拟渲染产出热力图而非 AI 画面 | 云 GPU / 远程推理 |
| 无实时渲染进度 | 当前为轮询假进度条 | WebSocket 推送真实进度 |

---

## 📄 License

MIT License. See [LICENSE](./LICENSE) for details.

---

<p align="center">
  <sub>Built with ❤️ using 3DGS + ControlNet + AnimateDiff + Three.js</sub>
</p>
