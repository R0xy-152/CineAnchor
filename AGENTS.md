# CineAnchor — 跨设备协作指引

## 项目简介

CineAnchor 是一个 AI 视频生成系统，用 3D Gaussian Splatting (3DGS) 作为空间锚点控制扩散模型渲染。技术栈：gsplat + ControlNet-Depth + FastAPI。

## 双设备分工

| 设备 | 职责 |
|------|------|
| **macOS (Apple M5)** — 当前机器 | API 开发、代码编辑、模拟测试、前端取景器、Git 管理 |
| **Windows (NVIDIA GPU)** — 你 | 真实 3DGS 渲染、深度图批量生成、ControlNet 推理 |

## 协作协议

1. **代码同步**：macOS 写代码 → `git push` → 你 `git pull` 后执行
2. **渲染任务**：macOS 给你下达渲染指令 → 你执行 → `git push` 产出（小文件）或 `rsync` 回传（大文件）
3. **你来写代码时**：直接改 → `git push` → 告诉 macOS 那边 `git pull`
4. **通信**：你的用户会给 macOS 那边的 Codex 传达消息，反之亦然。如果需要交流，把你的信息写在 `COLLAB_MSG.md` 里，macOS 那边会读到。

## Windows 环境配置

```bash
# 1. 克隆仓库 (如果还没克隆)
git clone git@github.com:R0xy-152/CineAnchor.git
cd CineAnchor

# 2. 创建 conda 环境
conda create -n cineanchor python=3.10 -y
conda activate cineanchor

# 3. PyTorch (CUDA 12.1)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 4. 核心依赖
pip install plyfile pillow numpy fastapi uvicorn pydantic

# 5. gsplat (预编译 wheel, 项目中可能有, 检查一下)
# 如果项目根目录有 gsplat-*.whl:
pip install gsplat-1.4.0+pt24cu121-cp310-cp310-win_amd64.whl
# 如果没有, 从源码编译:
# pip install -e gsplat/

# 6. 验证 CUDA
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

## 场景数据

PLY 文件不进 Git (太大)。每台设备本地生成：

```bash
python generate_cube_splat.py    # 生成 test_scene.ply (20000 个高斯点)
```

## 当前进度

- ✅ API 骨架 (main.py) — 路由完整
- ✅ 相机 → 深度图 pipeline (camera_to_depth_pipeline.py)
- ✅ real_3dgs.py view_matrix bug 已修复
- ✅ simulated_3dgs.py (macOS 开发用)
- ❌ 最小闭环未验证 — 从未在有效 PLY 上跑通过 gsplat 渲染
- ❌ ControlNet 扩散渲染 — simulated_diffusion.py 只是占位符

## 你的默认任务

**当没有新的指令时，你的工作是把 NVIDIA GPU 环境配置好，确保项目能跑通以下最小闭环：**

```
generate_cube_splat.py → test_scene.ply
    → real_3dgs.py → real_depth_maps/*.png (肉眼可辨认的深度图)
    → (未来) camera_to_depth_pipeline.py → 完整 Phase 1 流程
```

## 重要约定

- **不要在 Windows 上修改 macOS 正在开发的代码文件**（main.py, real_3dgs.py 等），除非用户明确要求
- **渲染产出放在本地输出目录**（.gitignore 已排除），不要提交到 Git
- **遇到问题先读 COLLAB_MSG.md**，macOS 那边的 Codex 可能留了消息
- **做完任务后，在 COLLAB_MSG.md 里写一行结果**，格式：`[时间] 任务描述 → 结果`
