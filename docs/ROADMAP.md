# CineAnchor 开发路线图

## 产品核心指标

唯一北极星指标：**用户能否在 3D 空间中像导演一样控制 AI 视频的镜头运动？**

辅助指标：
- 从 prompt 到可预览 3D 场景的时间 < 30s
- 深度图渲染 100+ 唯一层级
- 相机路径可完全复用 (saved → loaded → rendered)
- Timeline 操作延迟 < 50ms

---

## Phase 1: 技术 MVP ✅ 已完成

| 模块 | 状态 | 产出 |
|------|------|------|
| Blender 场景生成 | ✅ | 2 场景 (禅园, 科幻走廊)，PBR 纹理 |
| Three.js 取景器 | ✅ | 3 相机模式，关键帧录制，GLB 加载 |
| 深度图渲染 | ✅ | Cycles 32 samples，100+ 层级 |
| Camera Timeline | ✅ | 拖拽关键帧，easing 曲线，播放/循环 |
| 实时深度预览 | ✅ | D 键切换，角落/全屏 |
| Camera Path CRUD | ✅ | 保存/加载/删除，SQLite 持久化 |
| Windows GPU 管线 | ✅ | gsplat + ControlNet + AnimateDiff |
| 文档 | ✅ | README, PRD, ARCHITECTURE, ROADMAP, HANDOFF |

---

## Phase 2: 创作工具完善 🔜 进行中

**目标：让用户能像用剪辑软件一样设计镜头。**

| 优先级 | 任务 | 预估 |
|--------|------|------|
| P1 | 补齐场景模板 (浮岛/沙漠/森林) | Windows 并行 |
| P1 | Camera Preset Library | Windows 并行 |
| P1 | 关键帧属性面板 (选中后编辑坐标/FOV) | 前端 |
| P2 | Timeline 缩放 (场景时长 >10s 时需要) | 前端 |
| P2 | 深度图预览接入真实 Blender 渲染数据 | 前后端 |
| P2 | 场景锚点自动检测 (识别 GLB 主体) | 后端 |
| P3 | HDRI 环境贴图 (Poly Haven) | 资源 |

---

## Phase 3: AI 渲染打通

**目标：端到端交付可导演的 AI 视频。**

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | 深度图质量持续优化 | EEVEE AOV / 对数编码 / 更高采样 |
| P1 | Windows 端全链路自动化 | API 触发 → 深度渲染 → ControlNet → MP4 |
| P2 | ComfyUI 工作流对接 | 替代 diffusers 脚本，更灵活的管线 |
| P2 | 即梦/Kling API 对接 | 国内用户的视频生成选项 |
| P3 | 多 pass 导出 (normal, segmentation) | 扩展 ControlNet 条件输入 |

---

## Phase 4: 产品化

**目标：从技术 Demo 变成可用的 Web 产品。**

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | 用户账户系统 | 注册/登录，OAuth |
| P1 | 作品库 | 保存/浏览 prompt + GLB + camera path + 视频 |
| P2 | 云 GPU 任务队列 | Celery/Redis，异步渲染，WebSocket 状态推送 |
| P2 | 镜头资产市场 | 社区分享/复用 camera path |
| P3 | UE5 Runtime Pipeline | 实时场景 + MetaHuman + Live Previs |

---

## 技术债务

| 项目 | 影响 | 计划 |
|------|------|------|
| Blender headless 冷启动 | 每次 +0.5s | Phase 3 改为常驻进程 |
| PBR 纹理不进 Git | 新开发者需手动下载 | 写下载脚本 |
| 前端单文件 ~1400 行 | 维护困难 | Phase 2 后拆分模块 |
| 旧版 API 端点未清理 | `/scene/create`, `/camera/record_frame` | 前端迁移完毕后删除 |
| `scene_templates.py` 已废弃 | 混淆 | Phase 2 后删除 |

---

## 不做的事

| 项目 | 原因 |
|------|------|
| 自研 Text-to-3D 模型 | 成本极高，Meshy/Tripo 已足够 |
| 自研 Diffusion | 完全错误的资源分配 |
| AI 自动运镜 | "镜头控制"是核心价值，不能交给 AI |
| 移动端 App / 小程序 | Web App 更适合 3D 取景器 + 视频预览 |
| 社区/社交功能 | 产品验证前太早 |
| 大型资产平台 | 太重，先验证核心价值 |
