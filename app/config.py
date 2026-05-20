import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
MODELS_DIR = STATIC_DIR / "models"
VIDEOS_DIR = STATIC_DIR / "videos"
DEPTH_DIR = BASE_DIR / "depth_maps"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
DEPTH_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("CINEANCHOR_DB", str(DATA_DIR / "cineanchor.db"))

MESHY_API_KEY = os.getenv("MESHY_API_KEY", "")
MESHY_API_BASE = "https://api.meshy.ai/v2"

# 渲染模式：local_gpu | cloud_modal | simulated
RENDER_MODE = os.getenv("CINEANCHOR_RENDER_MODE", "simulated")
