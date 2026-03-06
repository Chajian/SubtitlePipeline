"""配置项 — 模型、设备、字幕样式等"""

import glob
import os
import sys

# ── 将 pip 安装的 NVIDIA DLL 加入 PATH（Windows 需要） ─────────
if sys.platform == "win32":
    _sp = os.path.join(
        os.path.dirname(sys.executable), "Lib", "site-packages", "nvidia"
    )
    for _bin in glob.glob(os.path.join(_sp, "*", "bin")):
        os.environ["PATH"] = _bin + os.pathsep + os.environ.get("PATH", "")

try:
    import ctranslate2
    _cuda_types = ctranslate2.get_supported_compute_types("cuda")
    DEVICE = "cuda" if _cuda_types else "cpu"
except Exception:
    DEVICE = "cpu"

# ── Whisper 模型 ──────────────────────────────────────────────
MODEL_SIZE = "large-v3"          # tiny / base / small / medium / large-v3
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

# ── 语言 ──────────────────────────────────────────────────────
SOURCE_LANGUAGE = "zh"           # 源语言（中文）

# ── 输出 ──────────────────────────────────────────────────────
OUTPUT_DIR = "output"

# ── 硬字幕样式（ASS 格式） ────────────────────────────────────
SUBTITLE_STYLE = {
    "FontName":      "Microsoft YaHei",
    "FontSize":      20,
    "PrimaryColour": "&H00FFFFFF",   # 白色
    "OutlineColour": "&H00000000",   # 黑色描边
    "BorderStyle":   1,
    "Outline":       2,
    "Shadow":        0,
    "MarginV":       30,             # 底部边距
}
