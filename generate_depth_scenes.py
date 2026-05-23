"""
Generate clean, filled synthetic depth maps for 5 scenes.
Uses OpenCV drawing for crisp, dense geometric structure that ControlNet can read.
"""
import cv2
import numpy as np
from pathlib import Path
import os
import math

OUTPUT_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "demo_depth_frames"
W, H = 768, 512


def new_frame():
    """Create a new depth frame initialized to white (far)."""
    return np.full((H, W), 255, dtype=np.uint8)


def draw_ground(depth, y_horizon=350, brightness=180):
    """Draw ground plane gradient."""
    for y in range(y_horizon, H):
        t = (y - y_horizon) / (H - y_horizon)
        val = int(brightness + (40 - brightness) * t * t)
        depth[y, :] = np.minimum(depth[y, :], np.clip(val, 40, brightness))
    return depth


def draw_sky(depth, y_horizon=350):
    """Sky area stays white (far)."""
    return depth


def draw_circle_3d(depth, cx, cy, cz, radius_px, shade=0.7):
    """Draw a filled circle — closer objects are darker."""
    val = int(max(20, cz / 30.0 * 255 * shade))
    cv2.circle(depth, (int(cx), int(cy)), int(radius_px), val, -1, cv2.LINE_AA)
    return depth


def draw_ellipse_3d(depth, cx, cy, cz, rx, ry, angle=0, shade=0.7):
    """Draw a filled ellipse."""
    val = int(max(20, cz / 30.0 * 255 * shade))
    cv2.ellipse(depth, (int(cx), int(cy)), (int(rx), int(ry)), angle, 0, 360, val, -1, cv2.LINE_AA)
    return depth


def draw_rect_3d(depth, cx, cy, cz, w, h, angle=0, shade=0.7):
    """Draw a filled rectangle."""
    val = int(max(20, cz / 30.0 * 255 * shade))
    box = cv2.boxPoints(((int(cx), int(cy)), (int(w), int(h)), angle))
    cv2.fillPoly(depth, [box.astype(np.int32)], val, cv2.LINE_AA)
    return depth


def draw_cone_3d(depth, cx, cy_top, cz, cy_bot, r_top, r_bot, shade=0.7):
    """Draw a trapezoid representing a cone/frustum."""
    val = int(max(20, cz / 30.0 * 255 * shade))
    pts = np.array([
        [cx - r_bot, cy_bot],
        [cx + r_bot, cy_bot],
        [cx + r_top, cy_top],
        [cx - r_top, cy_top],
    ], dtype=np.int32)
    cv2.fillPoly(depth, [pts], val, cv2.LINE_AA)
    return depth


def apply_blur(depth, ksize=3):
    """Light blur to smooth edges."""
    return cv2.GaussianBlur(depth, (ksize, ksize), 0)


# ═══════════════════════════════════════════════════════════
# Scene generators — return list of draw functions
# ═══════════════════════════════════════════════════════════

def gen_zen_garden(t):
    """t: 0→1 camera progress"""
    depth = new_frame()
    # Ground
    draw_ground(depth, y_horizon=280, brightness=160)
    # Sky
    draw_sky(depth, y_horizon=280)

    # Camera pans from right to center, getting closer
    cam_dx = 300 * (1 - t)
    cam_dy = 150 * (1 - t)
    scale = 0.5 + 0.5 * t  # zoom in

    # Trees (cylinders + cones) — 5 trees at various positions
    tree_positions = [(-200, -50, 12), (-50, -80, 10), (80, -40, 14), (200, -60, 11), (-120, 40, 13)]
    for bx, by, bz in tree_positions:
        sx = W/2 + (bx + cam_dx) * scale
        sy = 280 + (by + cam_dy) * scale
        tr_h = 80 * scale
        cr_h = 60 * scale
        tr_w = 8 * scale
        cr_w = 40 * scale
        # Trunk
        draw_rect_3d(depth, sx, sy, bz, tr_w, tr_h, 0, shade=0.6)
        # Crown
        draw_ellipse_3d(depth, sx, sy - tr_h/2 - cr_h/2, bz * 0.8, cr_w, cr_h, 0, shade=0.75)

    # Rocks — scattered
    rock_positions = [(-150, 20, 6), (100, -100, 7), (50, 80, 5), (-80, -30, 8), (180, 20, 6)]
    for rx, ry, rz in rock_positions:
        sx = W/2 + (rx + cam_dx) * scale
        sy = 280 + (ry + cam_dy) * scale
        r = 12 * scale * (rz / 10)
        draw_circle_3d(depth, sx, sy, rz, r, shade=0.5)

    # Pond
    px, py = W/2 + (50 + cam_dx) * scale, 280 + (-80 + cam_dy) * scale
    draw_ellipse_3d(depth, px, py, 4, 60 * scale, 30 * scale, -10, shade=0.4)

    # Bridge
    draw_rect_3d(depth, px, py - 5 * scale, 4.5, 80 * scale, 8 * scale, 10, shade=0.45)

    return apply_blur(depth)


def gen_scifi_corridor(t):
    """Corridor receding into depth."""
    depth = new_frame()

    # Vanishing point
    vp_x = W/2
    vp_y = H * 0.38

    # Corridor gets wider as camera moves forward
    scale = 0.3 + 0.5 * t

    # Floor
    floor_pts = np.array([
        [vp_x - 350 * scale, H],
        [vp_x + 350 * scale, H],
        [vp_x + 5, vp_y],
        [vp_x - 5, vp_y],
    ], dtype=np.int32)
    cv2.fillPoly(depth, [floor_pts], 100, cv2.LINE_AA)

    # Ceiling
    ceil_pts = np.array([
        [vp_x - 350 * scale, 0],
        [vp_x + 350 * scale, 0],
        [vp_x + 5, vp_y],
        [vp_x - 5, vp_y],
    ], dtype=np.int32)
    cv2.fillPoly(depth, [ceil_pts], 130, cv2.LINE_AA)

    # Left wall
    lw_pts = np.array([
        [vp_x - 350 * scale, H],
        [vp_x - 350 * scale, 0],
        [vp_x - 5, vp_y],
        [vp_x - 5, vp_y],
    ], dtype=np.int32)
    cv2.fillPoly(depth, [lw_pts], 85, cv2.LINE_AA)

    # Right wall
    rw_pts = np.array([
        [vp_x + 350 * scale, H],
        [vp_x + 350 * scale, 0],
        [vp_x + 5, vp_y],
        [vp_x + 5, vp_y],
    ], dtype=np.int32)
    cv2.fillPoly(depth, [rw_pts], 85, cv2.LINE_AA)

    # Pillars along walls
    for i in range(6):
        z = 0.15 + i * 0.13
        sx_l = vp_x - 350 * scale + (vp_x - 5 - (vp_x - 350 * scale)) * z
        sx_r = vp_x + 350 * scale + (vp_x + 5 - (vp_x + 350 * scale)) * z
        sy = H - (H - vp_y) * z
        pw = max(3, 15 * (1 - z))
        ph = max(10, 100 * (1 - z))
        cv2.rectangle(depth, (int(sx_l - pw/2), int(sy - ph)), (int(sx_l + pw/2), int(sy)),
                      int(60 + z * 100), -1, cv2.LINE_AA)
        cv2.rectangle(depth, (int(sx_r - pw/2), int(sy - ph)), (int(sx_r + pw/2), int(sy)),
                      int(60 + z * 100), -1, cv2.LINE_AA)

    # Floor lines (perspective)
    for i in range(12):
        z = 0.05 + i * 0.075
        x_l = vp_x - 350 * scale + (vp_x - 3 - (vp_x - 350 * scale)) * z
        x_r = vp_x + 350 * scale + (vp_x + 3 - (vp_x + 350 * scale)) * z
        y = H - (H - vp_y) * z
        cv2.line(depth, (int(x_l), int(y)), (int(x_r), int(y)), int(80 + z * 80), 1, cv2.LINE_AA)

    # End of corridor glow
    cv2.circle(depth, (int(vp_x), int(vp_y)), 8, 70, -1, cv2.LINE_AA)
    cv2.circle(depth, (int(vp_x), int(vp_y)), 15, 110, -1, cv2.LINE_AA)

    return apply_blur(depth, 3)


def gen_floating_islands(t):
    """Multiple islands floating at different heights."""
    depth = new_frame()

    # Sky gradient
    for y in range(H):
        depth[y, :] = int(220 + 35 * y / H)

    scale = 0.6 + 0.4 * t
    cam_dx = 400 * (1 - t)
    cam_dy = 200 * (1 - t)

    islands = [
        (W/2, H/2, 3.0, 120, 0),
        (W/2 + 180, H/2 - 60, 2.0, 80, -20),
        (W/2 - 150, H/2 + 40, 2.5, 90, 10),
        (W/2 + 100, H/2 + 80, 1.8, 65, 5),
        (W/2 - 200, H/2 - 80, 2.2, 75, -15),
    ]

    for cx, cy, z, r, angle in islands:
        sx = cx + cam_dx * scale
        sy = cy + cam_dy * scale
        sr = r * scale
        # Island top
        draw_ellipse_3d(depth, sx, sy, z, sr, sr * 0.25, angle, shade=0.45)
        # Island base (cone underside)
        draw_cone_3d(depth, sx, sy + sr * 0.25, z * 1.2, sy + sr * 0.25 + 60 * scale,
                     sr * 0.7, sr * 0.3, shade=0.6)

    # Crystals on islands
    for _ in range(8):
        ix = np.random.choice([i[0] for i in islands]) + np.random.uniform(-40, 40)
        iy = np.random.choice([i[1] for i in islands]) + np.random.uniform(-10, 10)
        h = np.random.uniform(15, 30) * scale
        sx = ix + cam_dx * scale
        sy = iy + cam_dy * scale
        draw_cone_3d(depth, sx, sy - h, 2, sy, 3 * scale, 0, shade=0.4)

    return apply_blur(depth)


def gen_desert_ruins(t):
    """Desert with pyramid, columns, obelisks."""
    depth = new_frame()

    # Sand ground
    draw_ground(depth, y_horizon=270, brightness=170)
    draw_sky(depth, y_horizon=270)

    scale = 0.6 + 0.4 * t
    cam_dx = 350 * (1 - t)
    cam_dy = 150 * (1 - t)

    # Pyramid at center
    px, py = W/2, 270
    sx = px + cam_dx * scale
    sy = py + cam_dy * scale
    # 3D pyramid: trapezoid (wider base, narrower top)
    pw_base = 140 * scale
    pw_top = 10 * scale
    ph = 140 * scale
    pts = np.array([
        [sx - pw_base, sy],
        [sx + pw_base, sy],
        [sx + pw_top, sy - ph],
        [sx - pw_top, sy - ph],
    ], dtype=np.int32)
    cv2.fillPoly(depth, [pts], 50, cv2.LINE_AA)
    # Pyramid cap
    cv2.circle(depth, (int(sx), int(sy - ph - 2 * scale)), int(5 * scale), 40, -1, cv2.LINE_AA)

    # Columns in a circle
    for i in range(8):
        a = i * math.pi / 4
        r = 160 * scale
        cx = sx + r * math.cos(a)
        cy = sy + r * math.sin(a) * 0.3
        ch = 100 * scale
        cw = 12 * scale
        draw_rect_3d(depth, cx, cy, 5, cw, ch, 0, shade=0.55)

    # Obelisks
    for i in range(3):
        a = i * 2 * math.pi / 3 + math.pi / 7
        r = 220 * scale
        cx = sx + r * math.cos(a)
        cy = sy + r * math.sin(a) * 0.3
        draw_rect_3d(depth, cx, cy - 30 * scale, 3, 10 * scale, 80 * scale, 0, shade=0.5)
        # Sun disk on one obelisk
        if i == 1:
            cv2.circle(depth, (int(cx), int(cy - 90 * scale)), int(15 * scale), 70, -1, cv2.LINE_AA)

    # Sun in sky
    cv2.circle(depth, (W - 80, 60), 35, 60, -1, cv2.LINE_AA)

    return apply_blur(depth)


def gen_forest_glade(t):
    """Forest with trees, ground, stone circle."""
    depth = new_frame()

    # Ground
    draw_ground(depth, y_horizon=300, brightness=180)
    draw_sky(depth, y_horizon=300)

    scale = 0.5 + 0.5 * t
    cam_dx = 300 * (1 - t)
    cam_dy = 150 * (1 - t)

    center_x = W/2
    center_y = 300

    # Trees (trunk + crown)
    tree_positions = []
    for _ in range(15):
        tx = np.random.uniform(-250, 250)
        ty = np.random.uniform(-150, 150)
        if abs(tx) < 60 and abs(ty) < 60:
            tx = np.random.choice([np.random.uniform(-250, -80), np.random.uniform(80, 250)])
        tree_positions.append((tx, ty, np.random.uniform(8, 16)))

    for tx, ty, tz in tree_positions:
        sx = center_x + (tx + cam_dx) * scale
        sy = center_y + (ty + cam_dy) * scale
        tr_h = np.random.uniform(80, 140) * scale
        tr_w = np.random.uniform(4, 10) * scale
        cr_h = np.random.uniform(50, 90) * scale
        cr_w = np.random.uniform(25, 55) * scale
        # Trunk
        draw_rect_3d(depth, sx, sy, tz, tr_w, tr_h, np.random.uniform(-3, 3), shade=0.6)
        # Crown layers
        for tier in range(np.random.randint(2, 4)):
            cy = sy - tr_h/2 - cr_h/2 - tier * cr_h * 0.5
            draw_ellipse_3d(depth, sx, cy, tz * (0.6 + 0.3 * tier), cr_w, cr_h, 0, shade=0.75)

    # Stone circle
    for i in range(12):
        a = i * math.pi / 6
        r = 70 * scale
        sx = center_x + r * math.cos(a)
        sy = center_y + r * math.sin(a) * 0.4
        draw_rect_3d(depth, sx, sy, 3, 8 * scale, np.random.uniform(20, 35) * scale, 0, shade=0.5)

    # God rays from top
    for i in range(5):
        rx = W/2 + np.random.uniform(-80, 80)
        cv2.line(depth, (int(rx), 0), (int(center_x + np.random.uniform(-80, 80)), H),
                 120, 2, cv2.LINE_AA)

    return apply_blur(depth)


# ═══════════════════════════════════════════════════════════
# Generate all frames
# ═══════════════════════════════════════════════════════════

SCENES = {
    "zen_garden": gen_zen_garden,
    "scifi_corridor": gen_scifi_corridor,
    "floating_islands": gen_floating_islands,
    "desert_ruins": gen_desert_ruins,
    "forest_glade": gen_forest_glade,
}

for scene_name, generator in SCENES.items():
    print(f"\n{'='*60}")
    print(f"  {scene_name}")
    print(f"{'='*60}")

    scene_dir = OUTPUT_DIR / scene_name
    scene_dir.mkdir(parents=True, exist_ok=True)
    for f in scene_dir.glob("*.png"):
        f.unlink()
    for f in scene_dir.glob("*.exr"):
        f.unlink()

    good_frames = 0
    for frame in range(24):
        t = frame / 23.0
        depth = generator(t)
        out_path = scene_dir / f"frame_{frame:04d}.png"
        cv2.imwrite(str(out_path), depth)

        uniq = len(np.unique(depth))
        if uniq > 20:
            good_frames += 1
        if frame % 4 == 0:
            print(f"  Frame {frame:02d}: unique={uniq}")

    print(f"  {good_frames}/24 frames with structure (unique>20)")

print("\nDone!")
