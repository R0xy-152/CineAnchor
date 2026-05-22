"""
Blender 场景生成器 — LLM 驱动的程序化 3D 场景生成

架构:
- 场景脚本: app/scenes/*.py (独立 bpy 脚本)
- 辅助库: app/scene_helpers.py (材质/光照/几何工具)
- 关键词匹配: 从 prompt 提取主题 → 选择脚本
- 可插拔 LLM: match_template() 可替换为 Anthropic/OpenAI API 调用

扩展路径 (生产环境):
  替换 match_template() → 调用 LLM API 直接生成 bpy 脚本
  无需模板库，AI 实时编写任何场景的 Python 代码
"""

import subprocess
import uuid
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from .config import BASE_DIR, MODELS_DIR

# 自动检测 Blender 路径 (macOS / Windows / Linux)
def _find_blender() -> str:
    import platform
    if platform.system() == "Windows":
        # 在 PATH 中搜索
        blender = shutil.which("blender")
        if blender:
            return blender
        # 常见安装路径 — glob 搜索
        import glob as _glob
        for p in _glob.glob("C:/Program Files/Blender Foundation/Blender */blender.exe"):
            return p
        return "blender"  # 让 subprocess 自己报错
    elif platform.system() == "Darwin":
        candidates = ["/opt/homebrew/bin/blender", "/Applications/Blender.app/Contents/MacOS/blender"]
        for c in candidates:
            if os.path.exists(c):
                return c
        return shutil.which("blender") or "blender"
    else:
        return shutil.which("blender") or "blender"

BLENDER_BIN = _find_blender()
SCENES_DIR = BASE_DIR / "app" / "scenes"

# ── 模板 → 脚本映射 ─────────────────────────────────────

TEMPLATE_SCRIPTS = {
    "zen_garden":        SCENES_DIR / "zen_garden.py",
    "scifi_corridor":    SCENES_DIR / "scifi_corridor.py",
    "floating_islands":  SCENES_DIR / "floating_islands.py",
    "desert_ruins":      SCENES_DIR / "desert_ruins.py",
    "forest_glade":      SCENES_DIR / "forest_glade.py",
}

# 只保留已实现的脚本
TEMPLATE_SCRIPTS = {k: v for k, v in TEMPLATE_SCRIPTS.items() if v.exists()}
if not TEMPLATE_SCRIPTS:
    raise RuntimeError("没有可用的场景模板，请检查 app/scenes/ 目录")

TEMPLATE_KEYWORDS = {
    "zen_garden":        ["禅", "日式", "花园", "庭院", "石头", "竹子", "枯山水", "zen", "japanese", "garden", "temple", "寺庙"],
    "scifi_corridor":    ["科幻", "走廊", "飞船", "金属", "霓虹", "未来", "scifi", "corridor", "spaceship", "neon", "赛博"],
    "floating_islands":  ["浮岛", "天空", "瀑布", "奇幻", "漂浮", "floating", "island", "sky", "fantasy", "waterfall", "仙境"],
    "desert_ruins":      ["沙漠", "遗迹", "金字塔", "埃及", "废墟", "desert", "ruins", "pyramid", "sand", "ancient"],
    "forest_glade":      ["森林", "树林", "阳光", "自然", "草地", "大树", "forest", "woods", "trees", "nature", "sunlight", "林地"],
}


def match_template(prompt: str) -> str:
    """关键词匹配 → 模板名。可替换为 LLM API 调用。"""
    lower = prompt.lower()
    scores = {}
    for name, keywords in TEMPLATE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[name] = score
    if not scores:
        return "zen_garden"
    return max(scores, key=scores.get)


def generate_scene(prompt: str, scene_id: Optional[str] = None) -> dict:
    """
    根据 prompt 生成 3D 场景 GLB 文件。

    流程:
    1. 关键词匹配 → 选择场景脚本
    2. 提取参数 → 写入 JSON
    3. Blender --background --python script.py -- params.json
    4. 返回 GLB 路径
    """
    template_name = match_template(prompt)
    script_path = TEMPLATE_SCRIPTS.get(template_name)
    if not script_path or not script_path.exists():
        # 回退到禅园
        script_path = TEMPLATE_SCRIPTS["zen_garden"]
        template_name = "zen_garden"

    scene_id = scene_id or str(uuid.uuid4())[:8]
    output_path = MODELS_DIR / f"blender_{scene_id}.glb"

    # 提取参数
    params = _extract_params(prompt)
    params["output_path"] = str(output_path)

    # 写入 JSON 参数文件
    params_path = Path(tempfile.gettempdir()) / f"cineanchor_params_{scene_id}.json"
    params_path.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

    # 设置环境变量让脚本能找到 app/
    env = os.environ.copy()
    env["CINEANCHOR_ROOT"] = str(BASE_DIR)

    try:
        result = subprocess.run(
            [BLENDER_BIN, "--background", "--python", str(script_path),
             "--", str(params_path)],
            capture_output=True, text=True, timeout=180,
            env=env, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            err = result.stderr[-800:] if result.stderr else "Unknown error"
            out = result.stdout[-400:] if result.stdout else ""
            return {"error": f"Blender 运行失败 (exit {result.returncode}):\nSTDERR: {err}\nSTDOUT: {out}"}

        if not output_path.exists():
            err = result.stderr[-800:] if result.stderr else ""
            out = result.stdout[-400:] if result.stdout else ""
            return {"error": f"脚本执行完成但未生成 GLB: {output_path}\nSTDERR: {err}\nSTDOUT: {out}"}

        return {
            "scene_id": scene_id,
            "model_path": str(output_path),
            "model_url": f"/static/models/{output_path.name}",
            "template": template_name,
            "prompt": prompt,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Blender 脚本执行超时 (180s)"}
    finally:
        if params_path.exists():
            params_path.unlink()


def _extract_params(prompt: str) -> dict:
    """从 prompt 提取简单参数"""
    params = {"prompt": prompt}

    color_match = re.search(r"(红|橙|黄|绿|蓝|紫|金|银|白|黑|粉)色", prompt)
    if color_match:
        params["accent_color"] = color_match.group(0)

    if any(w in prompt for w in ["夜晚", "晚上", "night", "暗"]):
        params["time_of_day"] = "night"
    elif any(w in prompt for w in ["黄昏", "傍晚", "sunset", "dusk"]):
        params["time_of_day"] = "sunset"
    else:
        params["time_of_day"] = "day"

    if any(w in prompt for w in ["大", "巨大", "庞大", "巨型", "large", "huge", "big"]):
        params["scale"] = 1.5
    elif any(w in prompt for w in ["小", "迷你", "tiny", "small"]):
        params["scale"] = 0.6
    else:
        params["scale"] = 1.0

    return params
