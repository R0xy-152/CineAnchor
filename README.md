
<p align="center">
  <img src="https://img.shields.io/badge/status-MVP-green" alt="MVP Ready">
  <img src="https://img.shields.io/badge/python-3.10-blue" alt="Python 3.10">
  <img src="https://img.shields.io/badge/CUDA-12.1-green" alt="CUDA 12.1">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License">
</p>

# 🎬 CineAnchor

**3D Gaussian Splatting as Spatial Anchor for Controllable AI Video Generation.**

CineAnchor 用 3D 高斯泼溅（3DGS）将三维场景嵌入扩散模型的生成过程 —— 你在 3D 取景器中构图，AI 用 ControlNet + AnimateDiff 逐帧生成风格化视频。

> **Demo:** 打开浏览器取景器 → 操控相机录制轨迹 → 一键生成 AI 视频。全程 API 驱动，macOS 前端 + NVIDIA GPU 后端协作。

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
- **跨平台双机协作**：macOS（API + 前端）↔ Windows/NVIDIA（GPU 推理）
- **自动环境检测**：有 GPU 用 gsplat + ControlNet，无 GPU 降级到 SDF 模拟
- **优雅降级**：ffmpeg → OpenCV → 帧序列，三级视频编码 fallback

---

## 🚀 快速开始

### 依赖

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121  # CUDA
pip install diffusers transformers accelerate gsplat plyfile pillow numpy
pip install fastapi uvicorn pydantic opencv-python
```

### macOS（前端 + 模拟管线）

```bash
python3 main.py                        # 启动 API (http://localhost:8001)
open http://localhost:8001             # 打开取景器
```

录制帧 → 点击"生成视频" → 输出 MP4。macOS 用 SDF 光线步进模拟深度渲染。

### Windows/NVIDIA（真实 GPU 管线）

```bash
python generate_cube_splat.py          # 生成 3DGS 场景 (PLY)
python e2e_test.py --sd15              # 运行端到端测试，输出 MP4
```

---

## 📁 项目结构

```
CineAnchor/
├── main.py                   # FastAPI 服务器，所有 API 路由
├── viewfinder.html           # 3D 取景器前端 (Three.js)
├── real_3dgs.py              # gsplat 3DGS 渲染器 (NVIDIA GPU)
├── controlnet_renderer.py    # ControlNet + AnimateDiff RGB 生成
├── video_renderer.py         # 渲染管线编排 + 视频合成
├── frame_interpolator.py     # RAFT 光流帧插值
├── simulated_3dgs.py         # SDF 光线步进模拟渲染 (macOS 开发)
├── generate_cube_splat.py    # PLY 场景生成器 (5 种变体)
├── e2e_test.py               # 端到端测试脚本
├── test_api.py               # API 自动化测试
└── COLLAB_MSG.md             # 双机协作通信板
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
