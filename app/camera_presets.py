"""
CineAnchor Camera Preset Library — 镜头语言预设

用户不需要手动调参数，而是选择"镜头语言"。
预设生成相对于场景主体的参数化相机行为。

用法:
    from app.camera_presets import PRESETS, apply_preset, list_presets

    keyframes = apply_preset("nolan_orbit", scene_center=[0, 0, 1.5], scene_radius=3.0)
    # 返回 [{t, pos, quat, fov}, ...]
"""

import math
from typing import Optional


def _quat_from_look(pos: list[float], target: list[float],
                    up: tuple = (0, 0, 1)) -> list[float]:
    """从相机位置和注视目标生成四元数 (x,y,z,w)。"""
    dx = target[0] - pos[0]
    dy = target[1] - pos[1]
    dz = target[2] - pos[2]
    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
    if dist < 1e-6:
        return [0, 0, 0, 1]
    forward = (dx/dist, dy/dist, dz/dist)

    # right = normalize(forward x up)
    rx = forward[1] * up[2] - forward[2] * up[1]
    ry = forward[2] * up[0] - forward[0] * up[2]
    rz = forward[0] * up[1] - forward[1] * up[0]
    rlen = math.sqrt(rx*rx + ry*ry + rz*rz)
    if rlen < 1e-6:
        rx, ry, rz = 1, 0, 0
    else:
        rx, ry, rz = rx/rlen, ry/rlen, rz/rlen

    # up_actual = normalize(right x forward)
    ux = ry * forward[2] - rz * forward[1]
    uy = rz * forward[0] - rx * forward[2]
    uz = rx * forward[1] - ry * forward[0]

    # 旋转矩阵 → 四元数
    trace = rx + uy - forward[2]
    if trace > 0:
        s = math.sqrt(trace + 1) * 2
        qw = 0.25 * s
        qx = (uz + forward[1]) / s
        qy = (forward[0] + rz) / s
        qz = (ry - rx) / s
    elif rx > uy and rx > -forward[2]:
        s = math.sqrt(1 + rx - uy + forward[2]) * 2
        qw = (uz + forward[1]) / s
        qx = 0.25 * s
        qy = (rx + ry) / s
        qz = (forward[0] + rz) / s
    elif uy > -forward[2]:
        s = math.sqrt(1 + uy - rx + forward[2]) * 2
        qw = (forward[0] + rz) / s
        qx = (rx + ry) / s
        qy = 0.25 * s
        qz = (uz + forward[1]) / s
    else:
        s = math.sqrt(1 + forward[2] + rx + uy) * 2
        qw = (ry - rx) / s
        qx = (forward[0] + rz) / s
        qy = (uz + forward[1]) / s
        qz = 0.25 * s

    qnorm = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    return [qx/qnorm, qy/qnorm, qz/qnorm, qw/qnorm]


# ═══════════════════════════════════════════════════════════
# 镜头预设库
# ═══════════════════════════════════════════════════════════

PRESETS = {
    "nolan_orbit": {
        "name": "Nolan Orbit",
        "description": "环绕主体 180°, 低角度仰拍, 缓慢推进。俯瞰 → 环绕 → 靠近",
        "params": {
            "orbit_angle": 180,
            "pitch": -15,
            "distance_ratio": 1.2,
            "duration": 6,
        },
    },
    "anime_closeup": {
        "name": "Anime Close-up",
        "description": "快速推近主体, 微幅晃动, 浅景深。从远处高速推进 → 贴身特写",
        "params": {
            "start_distance": 8,
            "end_distance": 2,
            "fov_start": 45,
            "fov_end": 35,
            "duration": 3,
        },
    },
    "dolly_reveal": {
        "name": "Dolly Reveal",
        "description": "侧向平移, 主体逐渐入画, 广角。摄像机横移暴露场景",
        "params": {
            "lateral_distance": 10,
            "fov": 70,
            "duration": 5,
        },
    },
    "drone_ascend": {
        "name": "Drone Ascend",
        "description": "从地面升到鸟瞰, 向下俯拍, 广角。垂直上升 + 缓慢前推",
        "params": {
            "start_height": 1.5,
            "end_height": 15,
            "fov": 60,
            "duration": 8,
        },
    },
    "hero_tracking": {
        "name": "Hero Tracking",
        "description": "从主体前方低角度跟拍, 后退拉开揭示环境。人物/物体出场方式",
        "params": {
            "start_distance": 3,
            "end_distance": 7,
            "pitch": -10,
            "duration": 5,
        },
    },
    "suspense_pan": {
        "name": "Suspense Pan",
        "description": "缓慢水平横扫, 制造悬疑感, 长焦。从左向右匀速摇镜",
        "params": {
            "pan_angle": 90,
            "fov": 35,
            "duration": 7,
        },
    },
    "god_eye": {
        "name": "God's Eye",
        "description": "极高鸟瞰, 极慢自转, 城市/大场景全景。正上方俯拍 + 缓慢旋转",
        "params": {
            "height_ratio": 6,
            "rotation_speed": 20,
            "fov": 50,
            "duration": 10,
        },
    },
    "whip_pan": {
        "name": "Whip Pan",
        "description": "快速甩镜, 镜头急转到另一侧。90° 快速切换视线方向",
        "params": {
            "swing_angle": 90,
            "fov": 55,
            "duration": 1.5,
        },
    },
}


def apply_preset(
    preset_name: str,
    scene_center: list[float],
    scene_radius: float,
    num_keyframes: Optional[int] = None,
) -> list[dict]:
    """
    根据预设名称 + 场景主体信息 → 生成关键帧列表。

    Args:
        preset_name: PRESETS 中的预设名称
        scene_center: 场景主体中心 [x, y, z]
        scene_radius: 场景包围球半径
        num_keyframes: 关键帧数量 (默认根据 duration 自动计算)

    Returns:
        [{t: 0.0, pos: [x,y,z], quat: [x,y,z,w], fov: 55}, ...]
    """
    if preset_name not in PRESETS:
        raise KeyError(
            f"Unknown preset '{preset_name}'. "
            f"Available: {list(PRESETS.keys())}"
        )

    preset = PRESETS[preset_name]
    params = preset["params"]
    duration = params.get("duration", 5)
    nk = num_keyframes or max(3, duration * 2)
    cx, cy, cz = scene_center
    r = scene_radius

    keyframes = []

    if preset_name == "nolan_orbit":
        orbit = math.radians(params["orbit_angle"])
        pitch = math.radians(params["pitch"])
        dist = r * params["distance_ratio"]

        for i in range(nk):
            t = i / (nk - 1)
            angle = math.pi / 2 - orbit / 2 + t * orbit
            px = cx + math.cos(angle) * dist
            py = cy + math.sin(angle) * dist
            pz = cz + math.sin(pitch) * dist
            pos = [px, py, pz]
            look = [cx, cy, cz * 0.7]
            quat = _quat_from_look(pos, look)
            keyframes.append({
                "t": round(t * duration, 2),
                "pos": [round(v, 3) for v in pos],
                "quat": [round(q, 4) for q in quat],
                "fov": 50,
            })

    elif preset_name == "anime_closeup":
        d_start = r * params["start_distance"]
        d_end = r * params["end_distance"]
        fov_s = params["fov_start"]
        fov_e = params["fov_end"]

        for i in range(nk):
            t = i / (nk - 1)
            # ease-in 加速推进
            et = t * t * (3 - 2 * t)  # smoothstep 反转 (先慢后快)
            dist = d_start + (d_end - d_start) * et
            fov = fov_s + (fov_e - fov_s) * t
            # 微幅水平晃动
            wobble = math.sin(t * 7) * 0.15 * r * (1 - t)
            px = cx - dist
            py = cy + wobble
            pz = cz + r * 0.4
            pos = [px, py, pz]
            look = [cx, cy, cz + r * 0.3]
            quat = _quat_from_look(pos, look)
            keyframes.append({
                "t": round(t * duration, 2),
                "pos": [round(v, 3) for v in pos],
                "quat": [round(q, 4) for q in quat],
                "fov": round(fov, 1),
            })

    elif preset_name == "dolly_reveal":
        lat = r * params["lateral_distance"]
        fov = params["fov"]

        for i in range(nk):
            t = i / (nk - 1)
            px = cx - lat * (1 - t) + lat * 0.3 * t
            py = cy + lat * 0.5 * (1 - t) - lat * 0.5 * t
            pz = cz + r * 0.6
            pos = [px, py, pz]
            look = [cx, cy, cz + r * 0.2]
            quat = _quat_from_look(pos, look)
            keyframes.append({
                "t": round(t * duration, 2),
                "pos": [round(v, 3) for v in pos],
                "quat": [round(q, 4) for q in quat],
                "fov": fov,
            })

    elif preset_name == "drone_ascend":
        h_start = r * params["start_height"]
        h_end = r * params["end_height"]
        fov = params["fov"]

        for i in range(nk):
            t = i / (nk - 1)
            pz = h_start + (h_end - h_start) * t
            # 缓慢前推 + 轻微侧移
            px = cx - r * 2 * (1 - t)
            py = cy - r * 1.5 * t
            pos = [px, py, pz]
            look = [cx, cy, cz + r * 0.3]
            quat = _quat_from_look(pos, look)
            keyframes.append({
                "t": round(t * duration, 2),
                "pos": [round(v, 3) for v in pos],
                "quat": [round(q, 4) for q in quat],
                "fov": fov,
            })

    elif preset_name == "hero_tracking":
        d_start = r * params["start_distance"]
        d_end = r * params["end_distance"]
        pitch = math.radians(params["pitch"])

        for i in range(nk):
            t = i / (nk - 1)
            dist = d_start + (d_end - d_start) * t
            px = cx - dist * math.cos(pitch)
            py = cy
            pz = cz + dist * math.sin(-pitch)
            pos = [px, py, pz]
            look = [cx, cy, cz + r * 0.4]
            quat = _quat_from_look(pos, look)
            keyframes.append({
                "t": round(t * duration, 2),
                "pos": [round(v, 3) for v in pos],
                "quat": [round(q, 4) for q in quat],
                "fov": 45,
            })

    elif preset_name == "suspense_pan":
        pan = math.radians(params["pan_angle"])
        fov = params["fov"]
        dist = r * 3.5

        for i in range(nk):
            t = i / (nk - 1)
            angle = -pan / 2 + t * pan
            px = cx + math.sin(angle) * dist
            py = cy - math.cos(angle) * dist
            pz = cz + r * 0.5
            pos = [px, py, pz]
            look = [cx, cy, cz + r * 0.3]
            quat = _quat_from_look(pos, look)
            keyframes.append({
                "t": round(t * duration, 2),
                "pos": [round(v, 3) for v in pos],
                "quat": [round(q, 4) for q in quat],
                "fov": fov,
            })

    elif preset_name == "god_eye":
        height = r * params["height_ratio"]
        rot_speed = math.radians(params["rotation_speed"])
        fov = params["fov"]

        for i in range(nk):
            t = i / (nk - 1)
            angle = t * rot_speed
            px = cx + math.cos(angle) * r * 0.3
            py = cy + math.sin(angle) * r * 0.3
            pz = cz + height
            pos = [px, py, pz]
            look = [cx, cy, cz]
            quat = _quat_from_look(pos, look)
            keyframes.append({
                "t": round(t * duration, 2),
                "pos": [round(v, 3) for v in pos],
                "quat": [round(q, 4) for q in quat],
                "fov": fov,
            })

    elif preset_name == "whip_pan":
        swing = math.radians(params["swing_angle"])
        fov = params["fov"]
        dist = r * 3

        for i in range(nk):
            t = i / (nk - 1)
            # 缓入缓出 (ease-in-out)
            et = t * t * (3 - 2 * t)
            angle = swing * (et - 0.5)
            px = cx + math.sin(angle) * dist
            py = cy - math.cos(angle) * dist
            pz = cz + r * 0.5
            pos = [px, py, pz]
            look = [cx, cy, cz + r * 0.2]
            quat = _quat_from_look(pos, look)
            keyframes.append({
                "t": round(t * duration, 2),
                "pos": [round(v, 3) for v in pos],
                "quat": [round(q, 4) for q in quat],
                "fov": fov,
            })

    return keyframes


def list_presets() -> list[dict]:
    """列出所有可用预设及其描述。"""
    return [
        {"id": k, "name": v["name"], "description": v["description"]}
        for k, v in PRESETS.items()
    ]


# ═══════════════════════════════════════════════════════════
# 独立测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    center = [0, 0, 1.5]
    radius = 3.0

    print("Camera Presets available:\n")
    for p in list_presets():
        print(f"  {p['id']:<18} {p['name']:<18} {p['description']}")

    print("\n" + "=" * 60)
    print(f"Testing all presets with center={center}, radius={radius}\n")

    for name in PRESETS:
        kf = apply_preset(name, center, radius)
        print(f"  {name}: {len(kf)} keyframes, "
              f"t=[{kf[0]['t']:.1f}→{kf[-1]['t']:.1f}], "
              f"fov={kf[0]['fov']}")
        # 验证四元数归一化
        for f in kf:
            q = f["quat"]
            mag = sum(x*x for x in q)
            if abs(mag - 1.0) > 0.01:
                print(f"    WARNING: non-unit quat at t={f['t']}: mag={mag:.4f}")

    print("\nDone.")
