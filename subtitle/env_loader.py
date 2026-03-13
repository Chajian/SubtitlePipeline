"""Helpers for loading local AI review environment files."""

from __future__ import annotations

import os
import re
from pathlib import Path

_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_env_file(path: str | Path, *, override: bool = False) -> list[str]:
    """Load simple KEY=VALUE pairs from a local env file."""
    env_path = Path(path)
    if not env_path.exists():
        return []

    loaded: list[str] = []
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not _ENV_NAME_RE.match(name):
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        if override or name not in os.environ:
            os.environ[name] = value
            loaded.append(name)

    return loaded


def bootstrap_ai_review_env(base_dir: str | Path) -> list[Path]:
    """Load local AI review env files before CLI args are parsed."""
    root = Path(base_dir)
    loaded_files: list[Path] = []

    common_path = root / ".env.ai-review.local"
    if load_env_file(common_path):
        loaded_files.append(common_path)

    provider = os.getenv("AI_REVIEW_PROVIDER", "").strip().lower()
    if not provider:
        return loaded_files

    provider_path = root / f".env.ai-review.{provider}.local"
    if load_env_file(provider_path):
        loaded_files.append(provider_path)

    return loaded_files
