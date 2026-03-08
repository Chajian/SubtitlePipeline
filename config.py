"""Project runtime configuration."""

from __future__ import annotations

import glob
import os
import sys

# On Windows, add NVIDIA runtime DLL paths installed by pip packages.
if sys.platform == "win32":
    site_packages = os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages", "nvidia")
    for bin_dir in glob.glob(os.path.join(site_packages, "*", "bin")):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

try:
    import ctranslate2

    _cuda_types = ctranslate2.get_supported_compute_types("cuda")
    DEVICE = "cuda" if _cuda_types else "cpu"
except Exception:
    DEVICE = "cpu"

# Whisper model config.
MODEL_SIZE = "large-v3"  # tiny / base / small / medium / large-v3
MODEL_SOURCE = "auto"  # auto / official / mirror / local
MODEL_DIR = None  # optional cache dir or local model dir
MODEL_MIRROR_ENDPOINT = None  # e.g. https://hf-mirror.com
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

# Input speech language.
SOURCE_LANGUAGE = "zh"
# Chinese subtitle script preference: simplified / traditional / raw.
CHINESE_SCRIPT = "simplified"

# Outputs.
OUTPUT_DIR = "output"

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
