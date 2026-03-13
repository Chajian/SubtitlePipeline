"""Project runtime configuration."""

from __future__ import annotations

import glob
import os
import sys

# On Windows, add NVIDIA runtime DLL paths installed by pip packages.
if sys.platform == "win32":
    venv_root = os.path.dirname(os.path.dirname(sys.executable))
    site_packages = os.path.join(venv_root, "Lib", "site-packages", "nvidia")
    for bin_dir in glob.glob(os.path.join(site_packages, "*", "bin")):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

try:
    import ctranslate2

    _cuda_types = ctranslate2.get_supported_compute_types("cuda")
    DEVICE = "cuda" if _cuda_types else "cpu"
except Exception:
    DEVICE = "cpu"

# Whisper model config.
MODEL_SIZE = "medium"  # tiny / base / small / medium / large-v3
MODEL_SOURCE = "auto"  # auto / official / mirror / local
MODEL_DIR = None  # optional cache dir or local model dir
MODEL_MIRROR_ENDPOINT = None  # e.g. https://hf-mirror.com
COMPUTE_TYPE = "int8_float16" if DEVICE == "cuda" else "int8"

# Input speech language.
SOURCE_LANGUAGE = "zh"
# Chinese subtitle script preference: simplified / traditional / raw.
CHINESE_SCRIPT = "simplified"

# Outputs.
OUTPUT_DIR = "output"

# AI subtitle review.
AI_REVIEW_MODE = "auto"  # auto / on / off
AI_REVIEW_PROVIDER = "codex"  # codex / openai / siliconflow
AI_REVIEW_COMMAND = "codex"
AI_REVIEW_MODEL = None  # optional codex model override
AI_REVIEW_BASE_URL = None  # optional OpenAI-compatible API base URL override
AI_REVIEW_MAX_BLOCKS_PER_CHUNK = 80
AI_REVIEW_MAX_CHARS_PER_CHUNK = 12_000
AI_REVIEW_TIMEOUT_SECONDS = 600
AI_REVIEW_MAX_ATTEMPTS = 2

# Hard subtitle style (ASS force_style fields).
SUBTITLE_STYLE = {
    "FontName": "Microsoft YaHei",
    "FontSize": 20,
    "PrimaryColour": "&H00FFFFFF",  # white
    "OutlineColour": "&H00000000",  # black outline
    "BorderStyle": 1,
    "Outline": 2,
    "Shadow": 0,
    "MarginV": 30,
}
