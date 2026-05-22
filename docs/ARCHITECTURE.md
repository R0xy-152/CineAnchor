# CineAnchor 技术架构

## 系统总览

```
用户 prompt → Blender 程序化生成 → GLB 3D 场景
                                    ↓
                          Three.js 取景器 (Web)
                          · 3 种相机模式
                          · 关键帧录制 + Timeline
                          · 实时深度预览 (MeshDepthMaterial)
                                    ↓
                          相机路径 JSON
                          · Catmull-Rom 插值
                          · easing 曲线
                                    ↓
                    ┌───────┴───────┐
                    ↓               ↓
              Blender headless     Three.js WebGL
              真实深度图 PNG       实时深度预览
              (Cycles 32 samples)  (D 键切换)
                    ↓
              ControlNet-Depth
              + AnimateDiff
              (Windows GPU)
                    ↓
              ffmpeg → MP4
```

## 核心技术决策

### 1. 为什么 Blender 而不是 UE5

| 维度 | Blender | UE5 |
|------|---------|-----|
| MVP 速度 | 快 — 纯 Python 脚本 | 慢 — C++/Blueprint |
| headless 渲染 | 原生 `--background` | 需 Pixel Streaming |
| Python 生态 | `bpy` 完整访问 | 有限的 Python API |
| 深度图导出 | Camera Data 节点 | SceneCapture 组件 |
| Web 集成 | subprocess 调用 | 极重 |
| 学习成本 | 低 | 高 |

**结论：** MVP 阶段 Blender 是正确的。UE5 在 Runtime Virtual Production 阶段（Phase 3+）更合适。

### 2. 为什么 Cycles 而不是 EEVEE 做深度渲染

| 维度 | Cycles | EEVEE |
|------|--------|-------|
| 深度精度 | 物理准确的光线追踪 | 光栅化近似 |
| 材质兼容 | Camera Data 节点精确 | 部分节点不支持 |
| 渲染速度 | 1-3s/帧 (32 samples) | <0.1s/帧 |
| 噪点 | 低采样有噪点 | 无噪点 |

**当前方案：** Cycles 32 samples + Filmic 色彩管理。实测 100+ 唯一深度层级。

**为什么不选 EEVEE：** EEVEE 的 Camera Data 节点输出精度较低（光栅化深度缓冲 → shader 采样 vs Cycles 的真实光线求交）。深度精度直接影响 ControlNet 的空间一致性。

**未来可能：** EEVEE + AOV (Arbitrary Output Variable) 方案值得探索，可能实现实时深度图导出。

### 3. 深度着色器设计

```
Camera Data → View Distance (世界单位, 米)
  → Math DIVIDE (÷ far_clip=25m)
  → Emission Strength (0..1)
  → Emission Color (1,1,1,1) × Strength
  → Film 色彩管理 (扩展色调范围)
  → 8-bit RGB PNG
```

**为什么用 Filmic 而不是 Raw：**
Raw 模式下线性深度值 0.0002-0.6 在 8-bit 输出中被压缩到 1-2 个层级。Filmic 的 lift/gamma/gain 曲线自然地扩展了暗部和中间调，使深度图在可见范围内有 100+ 层级。

**为什么不直接用 Z-pass：**
Blender 5.1 移除了 `scene.node_tree` 合成器 API。手动 Z-pass 导出需要 OpenEXR 文件 + 后处理，增加了复杂度。Emission shader 方案在 Blender 5.1 中最可靠。

### 4. 坐标系统转换

Three.js (Web) 使用 **Y-up**，Blender 使用 **Z-up**。GLB 导入 Blender 时自动 Y→Z 转换。

**相机位姿转换流程：**

```
Three.js 相机 (Y-up)
  position: (x, y, z)
  quaternion: (qx, qy, qz, qw)
    ↓ _three_to_blender_pose()
  Blender 相机 (Z-up)
  position: (x, -z, y)
  target: position + forward * 5m
```

四元数不能简单的分量交换。正确做法：从四元数计算前方向量 → 坐标转换 → 用 look-at 设置 Blender 相机旋转。

```python
# 从四元数计算前方向 (Three.js 相机前方向 = -Z)
fx = -2*(qx*qz + qw*qy)
fy = -2*(qy*qz - qw*qx)
fz = -1 + 2*(qx*qx + qy*qy)

# Y-up → Z-up 转换前方向
bfx, bfy, bfz = fx, -fz, fy

# Blender look-at
target = position + forward * 5.0
```

### 5. Catmull-Rom 插值

**为什么 Catmull-Rom 而不是线性/贝塞尔：**
- 线性插值在关键帧处速度突变（不连续的一阶导数）
- Catmull-Rom 保证 C¹ 连续（速度连续），相机运动更自然
- 四点插值（前后各一个控制点）自动计算切线，不需要手动设置贝塞尔手柄

**实现：**
```
给定 4 个控制点 P0, P1, P2, P3 和局部参数 t∈[0,1]:
  pos(t) = 0.5 * (
    (2*P1) +
    (-P0 + P2) * t +
    (2*P0 - 5*P1 + 4*P2 - P3) * t² +
    (-P0 + 3*P1 - 3*P2 + P3) * t³
  )
```

**Easing 叠加：** 时间 easing (ease-in/out) 作用于 Catmull-Rom 的局部参数 t，实现非线性时间映射。空间路径仍然由 Catmull-Rom 保证平滑。

### 6. PBR 纹理管线

纹理来自 ambientCG (CC0 协议)。每套纹理集包含 Color、NormalGL、Displacement、Roughness、Metalness JPG。

**Blender Shader Node 图：**
```
UV → Mapping (scale) → TexImage (Color)  ─→ BSDF Base Color
                      → TexImage (Rough)  ─→ BSDF Roughness
                      → TexImage (Metal)  ─→ BSDF Metallic
                      → TexImage (Normal) → NormalMap → BSDF Normal
                      → TexImage (Disp)   → Displacement → Output
```

**Blender 5.1 兼容性：**
- `image.colorspace_settings.name = 'Non-Color'` 替代已废弃的 `tex.color_space`
- `use_nodes = True` 在 5.1 中触发 DeprecationWarning（6.0 会移除），但功能正常

### 7. Mac / Windows 双设备架构

| 设备 | 职责 | 为什么 |
|------|------|--------|
| **macOS (M5)** | API 服务、Blender 场景生成、GLB 导出、深度图渲染、Web 前端 | Blender 5.1 原生运行，开发效率高 |
| **Windows (RTX 4060)** | gsplat 3DGS、ControlNet-Depth、AnimateDiff、ffmpeg | 需要 NVIDIA CUDA |

**同步方式：** Git (代码) + 本地文件系统 (大文件产出)

## 前端架构

### Three.js 取景器
- 3 种相机控制模式：Orbit (OrbitControls)、Drone (WASD 飞行)、FPS (第一人称)
- 关键帧录制：捕获 camera position + quaternion + FOV
- Timeline Canvas：自定义 2D Canvas 渲染，菱形关键帧节点可拖拽
- 实时深度预览：MeshDepthMaterial → offscreen RenderTarget → 角落窗口 / 全屏

### 前端-后端通信
- `POST /api/scenes/generate-blender` — 触发 Blender 场景生成
- `POST /api/camera-paths` — 保存运镜 (包括 easing 数据)
- `POST /api/camera-paths/{id}/render-depth` — 触发 Blender 深度渲染
- 所有 API 返回 JSON，前端 fetch + toast 通知

## 已识别的问题

1. **深度图质量因相机角度而异：** 正前方角度深度层级少（场景几何限制）。通过用户设计运镜时使用实时深度预览来缓解。
2. **Blender headless 启动慢：** 每次调用 ~0.5s 冷启动。未来可考虑 Blender Python 常驻进程。
3. **PBR 纹理不进 Git：** 58MB 纹理集需本地下载。在 README 中提供下载脚本。
