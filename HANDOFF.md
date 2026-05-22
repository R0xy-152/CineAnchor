# CineAnchor — Windows 端交接文档

## 项目概述

CineAnchor = AI 3D 场景导演工具。用户输入 prompt → AI 生成 3D 场景(GLB) → 在网页取景器中探索 → 设计相机运镜 → 渲染成视频。

**技术栈**: Blender Python (bpy) + Three.js + FastAPI + ControlNet/AnimateDiff + gsplat(3DGS)

## 当前状态总览

| 模块 | 状态 | 备注 |
|------|------|------|
| 服务器启动 | ✅ | `start_server.ps1` 一键启动 |
| 3D 场景生成 (Blender) | ✅ | 5 个模板: zen_garden, scifi_corridor, floating_islands, desert_ruins, forest_glade |
| 深度图渲染 | ✅ | 145 帧, 0-255 归一化 |
| 预览运镜 (Cycles GPU) | ✅ | 6 秒 145 帧, 场景居中 |
| AI 示例视频 | ✅ | 22 帧, 0.92s |
| 前端取景器 UI | ⚠️ | 刚重设计, 可能有 JS 报错 |
| ControlNet 批量渲染 | ✅ | batch_render_scenes.py |
| 3DGS 渲染 | ✅ | 需 CUDA 环境 |

## 环境配置

### 启动服务器
```powershell
# 在项目根目录
powershell -ExecutionPolicy Bypass -File start_server.ps1
```
服务器监听 `http://127.0.0.1:8001`。

start_server.ps1 设置了:
- CUDA_HOME = C:\Users\27079\miniconda3\Library
- MSVC 编译器路径 (gsplat JIT 编译需要)
- HTTP_PROXY = http://127.0.0.1:7890
- INCLUDE/LIB (Windows SDK 路径)

### Blender
- 路径: `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe`
- 代码中自动检测 (`app/blender_generator.py` 和 `app/depth_renderer.py`)

### GPU
- RTX 4060 8GB
- CUDA 12.4 (conda 安装)
- PyTorch cu124

### 关键依赖
- diffusers, transformers, accelerate (HuggingFace 模型已缓存)
- gsplat (JIT 编译, site-packages 有 3 处手动修改, 见下方)
- bpy (Blender Python, 随 Blender 安装)
- ffmpeg (winget 安装)

## 代码结构

```
CineAnchor/
├── main.py                    # FastAPI 服务器入口
├── app/
│   ├── blender_generator.py   # Blender 场景生成调度
│   ├── depth_renderer.py      # 深度图 + 预览渲染
│   ├── scene_manager.py       # 场景 CRUD
│   ├── camera_path.py         # 运镜路径 CRUD
│   ├── camera_presets.py      # 8 个镜头预设 (nolan_orbit 等)
│   ├── scene_helpers.py       # Blender 材质/光照工具
│   ├── scenes/
│   │   ├── zen_garden.py      # 日式禅园
│   │   ├── scifi_corridor.py  # 科幻走廊
│   │   ├── floating_islands.py
│   │   ├── desert_ruins.py
│   │   ├── forest_glade.py
│   │   ├── render_depth.py    # Blender 深度图渲染脚本
│   │   └── render_preview.py  # Blender 预览渲染脚本
│   └── config.py              # 路径配置
├── static/
│   ├── viewer.html            # 取景器 (主前端, 2100+ 行)
│   ├── index.html             # 产品首页
│   └── videos/                # Demo 视频
├── controlnet_renderer.py     # ControlNet + AnimateDiff
├── video_renderer.py          # ffmpeg 视频合成
├── frame_interpolator.py      # RAFT 光流插值
├── batch_render_scenes.py     # 批量 AI 渲染 5 场景
├── start_server.ps1           # 服务器启动脚本
└── HANDOFF.md                 # 本文档
```

## 已知 Windows 兼容性问题及修复

### 1. `/tmp` 不存在
Windows 没有 `/tmp`。改为 `tempfile.gettempdir()`。
- `app/blender_generator.py:113`
- `app/depth_renderer.py:214`

### 2. `Path.write_text()` 默认编码
Windows 默认编码是 GBK，Blender 读 UTF-8 → 乱码。加 `encoding="utf-8"`。
- `app/blender_generator.py:114`
- `app/depth_renderer.py:215`

### 3. `subprocess.run()` 编码
`text=True` 默认用系统编码 (GBK)，Blender 输出 UTF-8 → 解码崩溃。
加 `encoding="utf-8", errors="replace"`。
- `app/blender_generator.py:124`
- `app/depth_renderer.py:223`

### 4. Blender 路径
硬编码 `/opt/homebrew/bin/blender` (macOS)。改为自动检测:
- `app/blender_generator.py:26-47`
- `app/depth_renderer.py:22-40`

### 5. `material_procedural` 缺失
`scifi_corridor.py` 导入但 `scene_helpers.py` 未定义。已添加。
- `app/scene_helpers.py:177-227`

### 6. ffmpeg concat 缺 duration
concat 文件缺 `duration` 行 → 22 帧变 3 帧。
- `video_renderer.py:42-49`

### 7. 相机 look-at 目标不准
从四元数反推的 look-at 与实际场景中心有偏差。改为直接存 target 坐标。
- `static/viewer.html:1090-1093` (关键帧存 target)
- `app/depth_renderer.py:119-128` (直接坐标转换)

### 8. gsplat JIT 编译 (site-packages)
`C:\Users\27079\miniconda3\Lib\site-packages\gsplat\cuda\_backend.py`:
- `-Wno-attributes` → `/wd4100 /wd4996 /wd4456 /wd4457` (MSVC 不认 GCC 标志)
- 添加 `-ccbin=D:/VisualStudio/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64`
- 添加 conda CUDA lib 路径到 `extra_ldflags`
- **重要**: 如果 `pip install gsplat` 重新安装, 这些修改会丢失, 需重新应用

## 当前待修复问题

### 问题 1: 前端取景器 — 3D 画布空白 + API 检测卡住
**症状**: 打开 viewer.html 后, 中间 3D 画布区域空白, 右侧面板显示 "API: detecting..." 一直不变。
**可能原因**: 刚完成 UI 重设计 (左栏+右引导面板), 可能是 CSS z-index 或 JS 元素 ID 引用问题。
**诊断方向**:
1. F12 打开浏览器控制台, 看 JS 报错
2. 检查 `#canvas` 元素是否被 sidebar 遮挡 (z-index 问题)
3. 检查 `checkAPI()` 函数是否正常 fetch `/health`

### 问题 2: 深度图视觉效果偏暗
**症状**: 渲染出来的深度图肉眼看起来偏暗, 但数据范围已是 0-255。
**说明**: 深度图本质就是灰度图, ControlNet 可以正常使用。这是视觉预期问题, 非 bug。

### 问题 3: AI 渲染示例视频质量
**症状**: 22 帧 / 0.92 秒, 画面模糊, 不能清晰看场景。
**根因**: SD 1.5 模型 + 仅 8 帧 AnimateDiff 输入 + 低深度约束 (ratio ~1.2)。
**可能改善**: 增加 Conditioning Scale (>1.7)、更多关键帧、换 SDXL。

---
## 给其他 AI 的任务 Prompt

以下 prompt 可以直接复制给 Claude Code / Cursor / Copilot 等 AI 工具使用。

---

### Prompt 1: 修复取景器前端

```
我需要在 C:\Users\27079\CineAnchor 项目中修复 3D 取景器前端。

项目是 FastAPI + Three.js 的 AI 3D 场景导演工具。服务器运行在 http://127.0.0.1:8001。

当前问题: 打开 static/viewer.html 后, 3D 画布区域空白, 右侧面板 API 状态显示 "detecting..." 不更新。

最近做了 UI 重设计, 把原来的右侧面板拆分为左栏(场景生成/相机模式/运镜) + 右栏(工作流引导)。CSS 和 HTML 已重写, JS 基本保留。

请诊断并修复:
1. 检查浏览器控制台 JS 报错
2. 检查 Three.js canvas 是否被左栏遮挡
3. 检查 checkAPI() 是否正确更新 #api-status 元素
4. 检查是否有 JS 引用了旧的 CSS class 名 (如 .btn-preset -> .preset-btn, .btn-mode -> .mode-btn)

关键文件: static/viewer.html (约 2200 行, CSS + HTML + JS 都在一个文件里)

服务器启动: powershell -ExecutionPolicy Bypass -File start_server.ps1
```

---

### Prompt 2: 优化预览渲染质量

```
在 C:\Users\27079\CineAnchor 项目中优化预览视频渲染质量。

项目使用 Blender Python (bpy) 渲染 3D 场景预览视频。

当前配置 (app/depth_renderer.py 中 render_preview_video 函数):
- 分辨率: 640x480
- 引擎: CYCLES
- 采样: 16
- GPU: RTX 4060 8GB

Blender 脚本: app/scenes/render_preview.py

需要改进:
1. 提升分辨率到 1024x768 或更高
2. 增加采样数
3. 考虑使用 EEVEE 替代 Cycles 以加速 (但需要设置 light probes)
4. 添加抗锯齿

注意: 
- Blender 路径自动检测 (C:\Program Files\Blender Foundation\Blender 5.1\blender.exe)
- 渲染 145 帧, 需要平衡质量 vs 时间
- subprocess.run 需要 encoding="utf-8", errors="replace"
```

---

### Prompt 3: 优化 AI 渲染管线

```
在 C:\Users\27079\CineAnchor 项目中优化 ControlNet + AnimateDiff 渲染管线。

当前配置 (最优, 经验证):
- 模型: SD 1.5 + ControlNet-Depth
- conditioning_scale: 1.7
- seed: 42 (统一)
- steps: 25
- AnimateDiff motion adapter: guoyww/animatediff-motion-adapter-v1-5-2
- sequential_cpu_offload (节省 VRAM)

关键文件:
- controlnet_renderer.py: ControlNet + AnimateDiff 封装
- video_renderer.py: ffmpeg 视频合成 (stitch 方法已修复 concat duration)
- frame_interpolator.py: RAFT 光流插值 (3x)
- e2e_test.py: 端到端测试脚本

当前限制:
- 8 帧 AnimateDiff 输入, 22 帧 RAFT 3x 输出 → 仅 0.92 秒
- ratio ~1.2 (深度几何约束弱)
- RTX 4060 8GB VRAM

优化方向:
1. 增加输入帧数 (16 帧) → 更长视频
2. 调整 conditioning_scale (1.7→2.0 可能提升但风险时序崩坏)
3. 尝试 SDXL ControlNet (需要 ~7GB VRAM, cpu_offload 可跑)

GPU 环境:
- CUDA 12.4 (conda)
- MSVC 编译器在 D:\VisualStudio\
- gsplat site-packages 有手动补丁 (见 _backend.py 顶部的 3 处修改)
```

---

### Prompt 4: 完整功能清单和 API 端点

```
CineAnchor API 端点 (http://127.0.0.1:8001):

GET  /health                              # 健康检查
GET  /                                    # 重定向到首页
POST /api/scenes/generate                 # Meshy Text-to-3D (需 API key)
POST /api/scenes/generate-blender         # Blender 本地生成 3D 场景
GET  /api/scenes                          # 场景列表
GET  /api/scenes/{id}                     # 场景详情
POST /api/scenes/{id}/check              # 检查 Meshy 任务状态

POST /api/camera-paths                    # 保存运镜
GET  /api/camera-paths                    # 运镜列表
GET  /api/camera-paths/{id}               # 运镜详情
PUT  /api/camera-paths/{id}               # 更新运镜
DELETE /api/camera-paths/{id}            # 删除运镜
POST /api/camera-paths/{id}/render-depth  # 渲染深度图
POST /api/camera-paths/{id}/render-preview # 渲染预览视频

GET  /api/camera-presets                  # 镜头预设列表
GET  /api/demo/setup                      # Demo 模式初始化

静态文件: /static/ (index.html, viewer.html, videos/*.mp4)
深度图: /depth_maps/
视频: /videos/
```

---

## 快速验证命令

```bash
# 检查服务器
curl http://127.0.0.1:8001/health

# 生成一个场景
curl -X POST http://127.0.0.1:8001/api/scenes/generate-blender \
  -H "Content-Type: application/json" \
  -d '{"prompt":"zen garden"}'

# 查看场景列表
curl http://127.0.0.1:8001/api/scenes?status=ready

# 查看镜头预设
curl http://127.0.0.1:8001/api/camera-presets
```
