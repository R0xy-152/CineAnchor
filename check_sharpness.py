import cv2
import numpy as np
from pathlib import Path

old = {
    "zen_garden": 18444.3,
    "scifi_corridor": 4172.8,
    "floating_islands": 8017.8,
    "desert_ruins": 11796.5,
    "forest_glade": 21438.3,
}

print("%-20s | %10s | %10s | %10s" % ("Scene", "Old", "New", "Change"))
print("-" * 60)

for scene, old_mean in old.items():
    rgb_dir = Path("controlnet_output") / f"{scene}_rgb"
    frames = sorted(rgb_dir.glob("rgb_frame_*.png"))
    lap_vars = []
    for f in frames:
        img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            lap_vars.append(cv2.Laplacian(img, cv2.CV_64F).var())

    new_mean = np.mean(lap_vars)
    pct = (new_mean - old_mean) / old_mean * 100
    print("%-20s | %10.1f | %10.1f | %+9.1f%%" % (scene, old_mean, new_mean, pct))
