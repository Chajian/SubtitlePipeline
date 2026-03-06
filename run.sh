#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ $# -lt 1 ]; then
  echo "Usage: ./run.sh <video> [extra args]"
  echo "Example: ./run.sh source.mp4 --no-burn"
  exit 1
fi

if [ -x ".venv/bin/python" ]; then
  ./.venv/bin/python auto_subtitle.py "$@"
else
  python3 auto_subtitle.py "$@"
fi
