# CineAnchor 环境配置指南

## 双平台策略

| 平台 | 用途 | GPU 加速 |
|------|------|----------|
| **macOS (Apple M5)** | API 开发、前端调试、模拟渲染测试 | MPS (仅 PyTorch), gsplat 仅 CPU |
| **NVIDIA 笔记本 (Windows/Linux)** | 真实 3DGS 渲染、视频生成推理 | CUDA 全加速 |

---

## macOS 配置 (开发环境)

```bash
cd /Users/ming/projects/CineAnchor

# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装核心依赖
pip install fastapi uvicorn[standard] pydantic numpy pillow plyfile

# 3. 安装 PyTorch (macOS MPS 版本, 推理用)
pip install torch torchvision

# 4. gsplat CPU 模式 (慢但可调试)
pip install gsplat    # 或 pip install -e gsplat/

# 5. 验证
python -c "import torch; print(torch.__version__)"
python -c "import gsplat; print('gsplat OK')"

# 6. 启动开发服务器
python main.py
# 访问 http://localhost:8000/docs 查看 API 文档
```

## NVIDIA 笔记本配置 (渲染引擎)

```bash
# Windows (PowerShell 管理员)
# 1. 安装 CUDA 12.1 Toolkit
# 2. 安装 cuDNN

# 3. 创建 conda 环境
conda create -n cineanchor python=3.10
conda activate cineanchor

# 4. 安装 PyTorch (CUDA 版本)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 5. 安装 gsplat (预编译 wheel, 项目自带)
pip install gsplat-1.4.0+pt24cu121-cp310-cp310-win_amd64.whl

# 6. 安装其余依赖
pip install fastapi uvicorn pydantic numpy pillow plyfile

# 7. 验证 CUDA
python -c "import torch; print(torch.cuda.is_available())"  # 应输出 True
```

---

## 为什么 macOS 不能完全运行这个项目？

1. **gsplat 的 CUDA kernel**: gsplat 的核心光栅化 (`rasterization()`) 是用 CUDA C++ 写的，编译为 `.so`/`.dll`，只能调用 NVIDIA GPU 驱动
2. **macOS 无 CUDA 驱动**: Apple Silicon 不支持 CUDA，只能用 CPU fallback
3. **CPU 渲染速度**: 20000 个高斯点在 CPU 上渲染一帧可能需数秒甚至数十秒，无法满足交互需求

## 推荐的开发分工

```
macOS (Apple M5)                     NVIDIA 笔记本
─────────────────                    ──────────────
• main.py (API 开发)                 • real_3dgs.py (真实渲染)
• simulated_3dgs.py (逻辑测试)       • 3DGS 场景加载
• 前端 Three.js 取景器                • 批量深度图渲染
• 深度图序列 → 视频 (ControlNet)      • ControlNet + AnimateDiff 推理
• Git, 代码编辑, Prompt 工程          • 输出视频编码
```
