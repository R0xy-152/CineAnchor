# CineAnchor 项目交接文件

更新时间：2026-05-20 (晚)
项目路径：`/Users/ming/Projects/CineAnchor`

---

## 1. 项目目的

CineAnchor 是一个 **AI 3D 场景导演级运镜工具**。核心工作流：

```
用户输入 prompt（如"日式禅园 枯山水 黄昏"）
  → Blender 程序化生成 3D 场景 GLB
  → Three.js 网页取景器中预览场景
  → 用户操控摄像机 / 录制运镜轨迹
  → Blender 渲染真实深度图序列
  → (Windows) ControlNet-Depth + AnimateDiff → MP4 视频
```

**产品定位**：不是和 Sora/Runway 拼"最强视频生成模型"，而是做 **3D 场景里的镜头设计 + AI 渲染**。核心差异化在于用户可以像导演一样在 3D 空间里设计镜头运动，而非仅靠 prompt 抽卡。

---

## 2. 项目结构

```
CineAnchor/
├── main.py                    # FastAPI 服务入口 (port 8001)
├── real_3dgs.py               # GPU gsplat 3DGS 深度渲染 (Windows only)
├── simulated_3dgs.py          # macOS 模拟深度渲染 (SDF ray marching)
├── controlnet_renderer.py     # ControlNet-Depth + AnimateDiff (Windows)
├── video_renderer.py          # 视频管线编排 (深度→RGB→帧插值→MP4)
├── frame_interpolator.py      # RAFT 光流帧插值
├── e2e_test.py                # 端到端验证脚本
├── test_api.py                # API 自动化测试 (14 用例)
├── generate_cube_splat.py     # 3DGS PLY 点云生成器
├── camera_to_depth_pipeline.py # 参考管线实现与伪代码
│
├── app/                       # 后端包
│   ├── config.py              # 路径/环境变量配置
│   ├── database.py            # SQLite 连接管理 + 建表
│   ├── scene_manager.py       # 场景生命周期 (Blender + Meshy)
│   ├── meshy_client.py        # Meshy API v2 封装
│   ├── camera_path.py         # 相机路径 CRUD
│   ├── blender_generator.py   # 关键词匹配 → Blender 场景脚本调用
│   ├── depth_renderer.py      # Blender 深度图渲染管理器
│   ├── scene_helpers.py       # Blender bpy 辅助库 (PBR材质/光照/几何)
│   ├── scene_templates.py     # 旧版场景生成 (模板字符串方式，已废弃)
│   ├── scenes/                # Blender 独立脚本
│   │   ├── zen_garden.py      #   日式禅园 (PBR纹理)
│   │   ├── scifi_corridor.py  #   科幻走廊 (PBR纹理)
│   │   └── render_depth.py    #   深度图渲染脚本
│   └── textures/              # ambientCG CC0 PBR纹理集 (8套, ~58MB)
│       ├── Ground054/         #   沙地
│       ├── Ground044/         #   碎石
│       ├── Rock023/           #   岩石
│       ├── Rock032/           #   深色岩石
│       ├── Moss001/           #   苔藓
│       ├── Wood045/           #   竹/木
│       ├── Marble008/         #   大理石
│       └── Metal032/          #   金属
│
├── static/                    # 前端
│   ├── index.html             #   产品首页
│   ├── viewer.html            #   3D 取景器 + 相机录制 (主要前端)
│   ├── viewfinder.html        #   旧版取景器
│   └── models/                #   Blender 生成的 GLB 文件
│
├── data/                      # SQLite 数据库 + PLY 文件
├── docs/PRD.md                # 产品需求文档
├── depth_maps/                # 深度图输出目录
├── videos/                    # MP4 输出目录
├── README.md                  # 项目 README
├── CLAUDE.md                  # 双设备协作指引
└── COLLAB_MSG.md              # 跨设备消息板
```

---

## 3. 数据库

SQLite 文件：`data/cineanchor.db`

### scenes 表

| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | 如 `scene_8d6e13d3976f` |
| user_prompt | TEXT | 用户输入的自然语言 |
| meshy_task_id | TEXT | Meshy 任务 ID (可空) |
| status | TEXT | pending/generating/ready/failed |
| model_format | TEXT | 默认 'glb' |
| model_path | TEXT | GLB 文件本地路径 |
| thumbnail_path | TEXT | 缩略图路径 |
| error_message | TEXT | 错误信息 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### camera_paths 表

| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | 如 `path_xxxx` |
| scene_id | TEXT FK→scenes | 关联场景 |
| name | TEXT | 路径名称 |
| duration | REAL | 总时长(秒) |
| fps | INTEGER | 帧率 (默认 24) |
| camera_mode | TEXT | 相机模式 |
| interpolation | TEXT | 插值算法 (默认 catmull-rom) |
| keyframes | TEXT JSON | 关键帧数组 [{t, pos, quat, fov}] |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

## 4. API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 + GPU 状态 |
| POST | `/api/scenes/generate-blender` | Blender 程序化生成场景 |
| POST | `/api/scenes/generate` | Meshy API 生成场景 |
| GET | `/api/scenes` | 场景列表 |
| GET | `/api/scenes/{id}` | 场景详情 |
| POST | `/api/camera-paths` | 保存相机路径 |
| GET | `/api/camera-paths` | 相机路径列表 |
| GET | `/api/camera-paths/{id}` | 相机路径详情 |
| PUT | `/api/camera-paths/{id}` | 更新相机路径 |
| DELETE | `/api/camera-paths/{id}` | 删除相机路径 |

---

## 5. Blender 场景生成管线

### 工作流
1. 用户输入 prompt → `blender_generator.match_template()` 关键词匹配
2. 匹配到场景脚本（zen_garden / scifi_corridor / 等）
3. `_extract_params()` 提取 scale, time_of_day 等参数 → JSON
4. 调用 `blender --background --python scenes/xxx.py -- params.json`
5. 场景脚本用 `scene_helpers.py` 创建 PBR 材质/光照/相机
6. 导出 GLB → 返回路径 → 前端加载

### 场景脚本是独立的 bpy 程序
- 通过 `sys.path` 找到项目根目录
- 导入 `app.scene_helpers` 获取 PBR 材质、光照、相机工具
- 每个脚本可独立在 Blender 中运行

### PBR 纹理
- 来源：ambientCG (CC0 协议)
- 每个纹理集包含 Color, NormalGL, Displacement, Roughness, Metalness JPG
- `material_pbr()` 自动查找并构建完整 PBR 节点图
- 兼容 Blender 5.1 API（`colorspace_settings.name = 'Non-Color'`）

### 已实现的场景
- **禅园 (zen_garden.py)**：沙地+碎石地形、石组+苔藓、竹栅栏、大理石灯笼、水池、松树、踏脚石、地表散布。104 mesh 对象，46MB GLB
- **科幻走廊 (scifi_corridor.py)**：金属墙壁、霓虹灯带、天花板横梁、六角地板、管道、全息终端。81 mesh 对象，215KB GLB
- **浮岛/沙漠遗迹/森林空地**：已注册关键词但脚本尚未编写

---

## 6. 前端取景器 (viewer.html)

技术栈：原生 HTML+CSS+JS + Three.js CDN + GLTFLoader

### 功能
- **3D 场景预览**：加载 GLB，自动调整比例和居中
- **3 种相机模式**：
  - Orbit（轨道旋转，默认）
  - Drone（WASD 飞行 + Q/E 升降）
  - FPS（第一人称）
- **关键帧录制**：用户摆放相机 → 添加关键帧 → Catmull-Rom 插值 → 绿色轨迹线显示
- **深度图预览**：模态窗口显示已渲染的深度图
- **视频渲染触发**：调用后端 API 渲染视频
- **参数面板**：Prompt、FPS、Seed、Conditioning Scale
- **场景列表**：从 API 加载已生成的场景
- **相机路径管理**：保存/加载/更新运镜轨迹

### 坐标转换
- Three.js 使用 Y-up 坐标系
- Blender 使用 Z-up 坐标系
- `depth_renderer._three_to_blender_pose()` 处理转换

---

## 7. 深度图渲染模块 (当前工作中的重点)

### 架构
1. **`app/depth_renderer.py`**（Python 端）
   - 从 DB 获取 camera_path + scene
   - Catmull-Rom 插值关键帧 → 逐帧位姿
   - Three.js → Blender 坐标转换（Y-up → Z-up）
   - 调用 Blender 渲染深度图

2. **`app/scenes/render_depth.py`**（Blender 脚本）
   - 导入 GLB → 覆写所有 MESH 材质为深度着色器
   - 深度着色器：Camera Data → View Distance → ÷ far_clip → Emission Strength
   - Cycles 4 samples, 16-bit PNG 输出
   - 逐帧：创建相机 → 瞄准 → 渲染

### 当前状态 (v5)
- ✅ GLB 导入、材质覆写、相机瞄准、坐标转换
- ✅ 端到端流程：camera_path → 插值 → 渲染 → 后处理 → PNG
- ✅ API 端点 `POST /api/camera-paths/{path_id}/render-depth`
- ✅ 前端"渲染深度图"按钮已接入
- ✅ 深度图质量：**104 唯一值，范围 35-138 (8-bit)，每行 62-94 唯一值**（侧面角度）
- ⚠️ 深度精度因相机角度而异：正前方角度质量较低（场景几何限制）
- 🔜 可进一步优化：对数深度编码、EEVEE 实时预览、更多 samples

---

## 8. Windows GPU 管线 (用户另一台机器)

Windows 上运行真实 AI 推理：

```
generate_cube_splat.py → PLY 点云
  → real_3dgs.py (gsplat CUDA) → 真实深度图
  → controlnet_renderer.py (ControlNet-Depth + AnimateDiff) → RGB 帧
  → frame_interpolator.py (RAFT 光流) → 插值帧
  → ffmpeg → MP4 视频
```

- `e2e_test.py --sd15` 可验证全管线
- gsplat wheel 已在仓库中：`gsplat-1.4.0+pt24cu121-cp310-cp310-win_amd64.whl`
- 最优配置 (来自 tuning)：`conditioning_scale=1.21`, SD 1.5 + AnimateDiff

---

## 9. 已完成 vs 待完成

### ✅ 已完成
- FastAPI 服务 + 所有路由
- SQLite 数据库 + scenes/camera_paths 表
- Blender 程序化场景生成（2 个场景）
- PBR 纹理系统（8 套 ambientCG）
- Three.js 取景器（3 种模式 + 关键帧录制 + 轨迹显示）
- 相机路径持久化与 Catmull-Rom 插值
- 深度图渲染管线架构（Python 端完整）
- macOS 模拟渲染（simulated_3dgs.py）
- Windows GPU 全管线（gsplat + ControlNet + AnimateDiff）
- 帧插值 + ffmpeg 视频合成
- README + PRD 文档
- 双设备协作协议 (CLAUDE.md)

### ❌ 待完成
- **深度图质量**：render_depth.py 深度值精度不够，需要优化（可能改为 EEVEE / Mist Pass / 更多 samples）
- API 端点：`POST /api/camera-paths/{id}/render-depth` 未接入
- 前端：缺少"渲染深度图"按钮，深度图预览未接入真实数据
- 端到端测试：macOS Blender 深度图 → (Windows) ControlNet → 视频 链路未验证
- 场景脚本：floating_islands.py, desert_ruins.py, forest_glade.py 未编写
- HDRI 环境贴图：未下载 Poly Haven HDR
- 缺少：用户账户、作品库、社区、云 GPU 队列、生产部署

---

## 10. 运行方式

```bash
cd /Users/ming/Projects/CineAnchor

# 启动 API 服务
python3 main.py
# → http://localhost:8001

# 前端取景器
open http://localhost:8001/static/viewer.html

# 深度图渲染测试
python3 -c "
from app.depth_renderer import render_depth_maps
print(render_depth_maps('path_xxxx'))
"
```

**依赖**：Blender 5.1 (brew 安装于 `/opt/homebrew/bin/blender`)

---

## 11. 环境说明

- **当前机器**：Mac M5, macOS 25.5
- **另一台**：Windows, NVIDIA RTX 4060 Laptop
- **Blender**：5.1.2 (Homebrew)
- **Python**：系统 Python 3
- **代理**：本地 127.0.0.1:7897
- **GitHub**：https://github.com/R0xy-152/CineAnchor

---

## 12. 重要约定

- 不要修改或删除 `.env`、API key、token、secret
- 不要强制推送、不要跳过 git hooks
- 未跟踪文件不要随意删除（除非确认是临时文件）
- 产出物（深度图、视频）在 .gitignore 中，不提交
- 所有 AI 生成内容使用 CC0/MIT 兼容资源
- Blender 脚本必须兼容 Blender 5.1 API
