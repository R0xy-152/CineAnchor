# CineAnchor 部署指南

## 架构

```
┌─────────────────────┐     ┌──────────────────────┐
│  静态网站托管        │────▶│  GPU 后端服务器        │
│  (GitHub Pages/      │     │  (Windows + RTX 4060  │
│   Vercel/自有主机)   │     │   或云 GPU)           │
│                      │     │                      │
│  static/             │     │  FastAPI :8001        │
│  ├── index.html      │     │  Blender              │
│  ├── viewer.html     │     │  ControlNet/AnimateDiff│
│  └── videos/*.mp4    │     │  CUDA + gsplat        │
└─────────────────────┘     └──────────────────────┘
```

## 方案 A: 前端静态托管 + Windows 本地后端

适用: 后端跑在本地 Windows 机器, 前端部署到公网。

### 1. 后端 (Windows)
```powershell
# 启动后端 (保持运行)
cd C:\Users\27079\CineAnchor
powershell -ExecutionPolicy Bypass -File start_server.ps1
```

如果需要公网访问, 使用 Cloudflare Tunnel 或 ngrok:
```bash
# Cloudflare Tunnel (免费)
cloudflared tunnel --url http://localhost:8001

# 或 ngrok
ngrok http 8001
```
获得公网 URL 如 `https://cineanchor.ngrok.dev`

### 2. 前端部署
将 `static/` 目录上传到静态托管, 在 `index.html` 和 `viewer.html` 的 `<head>` 中添加:
```html
<script>window.CINEANCHOR_API = "https://你的后端URL";</script>
```

### 3. 部署到 GitHub Pages
```bash
cd C:\Users\27079\CineAnchor
# 创建部署分支
git checkout -b gh-pages
# 只保留 static/ 内容
# ... (或使用 GitHub Actions 自动部署)
```

## 方案 B: 全部部署到云 GPU

适用: 不需要本地机器, 全部上云。

推荐平台:
- **RunPod** (便宜 GPU, ~$0.44/h RTX 4090)
- **Modal** (按秒计费, 支持 Blender)
- **HuggingFace Spaces** (免费 CPU, 无 GPU)

### RunPod 部署步骤
1. 创建 GPU Pod (RTX 4090 / A4000)
2. 安装环境:
```bash
git clone https://github.com/R0xy-152/CineAnchor.git
cd CineAnchor
conda create -n cineanchor python=3.10 -y && conda activate cineanchor
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
# 安装 Blender
apt-get install -y blender  # Linux
```
3. 启动: `python main.py`
4. 暴露端口: RunPod 提供公网 URL

## 当前 Windows 后端地址

后端启动后, 本地地址: `http://127.0.0.1:8001`

公网地址需要通过 Cloudflare Tunnel / ngrok 获得。

## 前端文件清单

需要部署到静态网站的文件:
```
static/
├── index.html          # 产品首页 (完全独立)
├── viewer.html         # 3D 取景器
├── viewfinder.html     # 旧版取景框
├── demo_output.mp4     # 原始 Demo
└── videos/
    ├── zen_garden_demo.mp4       # 91 KB, 6s
    ├── scifi_corridor_demo.mp4   # 198 KB, 6s
    ├── floating_islands_demo.mp4 # 95 KB, 6s
    ├── desert_ruins_demo.mp4     # 27 KB, 6s
    └── forest_glade_demo.mp4     # 137 KB, 6s
```

总计: ~600 KB + HTML 文件

不需要: app/, main.py, *.py, data/, depth_maps/
