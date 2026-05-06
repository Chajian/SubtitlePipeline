from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DebugTrace:
    mode: str
    root: Path
    enabled: bool = True

    def write_manifest(self, payload: dict[str, Any]) -> None:
        if not self._should_write():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        self._manifest_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append_timeline(self, payload: dict[str, Any]) -> None:
        if not self._should_write():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        with self._timeline_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _should_write(self) -> bool:
        return self.enabled and self.mode == "web"

    def _manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def _timeline_path(self) -> Path:
        return self.root / "timeline.jsonl"
