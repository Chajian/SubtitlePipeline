#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

step() {
  echo
  echo "[setup] $1"
}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[error] python3 not found. Install Python 3.10+ first."
  exit 1
fi

step "Checking Python version"
"$PYTHON_BIN" - <<'PY'
import sys
assert sys.version_info >= (3, 10), "Python 3.10+ required"
print("Python", sys.version.split()[0])
PY

if [ ! -d ".venv" ]; then
  step "Creating virtual environment (.venv)"
  "$PYTHON_BIN" -m venv .venv
fi

step "Installing dependencies"
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    echo "[ok] ffmpeg found: $(ffmpeg -version | head -n 1)"
    return
  fi

  echo "[warn] ffmpeg not found in PATH."
  if [ "${SKIP_FFMPEG_INSTALL:-0}" = "1" ]; then
    echo "[warn] SKIP_FFMPEG_INSTALL=1 set. Install ffmpeg manually."
    return
  fi

  if command -v brew >/dev/null 2>&1; then
    echo "[setup] Installing ffmpeg via brew..."
    brew install ffmpeg
  elif command -v apt-get >/dev/null 2>&1; then
    echo "[setup] Installing ffmpeg via apt-get..."
    sudo apt-get update
    sudo apt-get install -y ffmpeg
  elif command -v dnf >/dev/null 2>&1; then
    echo "[setup] Installing ffmpeg via dnf..."
    sudo dnf install -y ffmpeg
  elif command -v pacman >/dev/null 2>&1; then
    echo "[setup] Installing ffmpeg via pacman..."
    sudo pacman -S --noconfirm ffmpeg
  else
    echo "[warn] Could not auto-install ffmpeg. Install manually: https://ffmpeg.org/download.html"
  fi
}

step "Checking ffmpeg"
ensure_ffmpeg

step "Done"
echo "Run command:"
echo "./.venv/bin/python ./auto_subtitle.py input.mp4"
echo
echo "Or use helper:"
echo "bash run.sh input.mp4"
