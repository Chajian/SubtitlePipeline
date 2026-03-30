"""Extract soft subtitle tracks as text segments."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from subtitle.srt import parse_srt_content


@dataclass(slots=True)
class SubtitleStream:
    """Metadata about a subtitle stream inside a container."""

    stream_index: int
    subtitle_index: int
    language: str | None


_PREFERRED_ZH = {"zh", "zho", "chi", "zh-cn", "zh-hans", "chs", "cht"}
_PREFERRED_EN = {"en", "eng"}


def _normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace("_", "-")


def list_subtitle_streams(video_path: str | Path) -> list[SubtitleStream]:
    """List subtitle streams with language metadata using ffprobe."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "s",
        "-show_entries",
        "stream=index:stream_tags=language",
        "-of",
        "json",
        str(video_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or "ffprobe failed"
        raise RuntimeError(details)

    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams", [])
    results: list[SubtitleStream] = []
    for subtitle_index, stream in enumerate(streams):
        if not isinstance(stream, dict):
            continue
        stream_index = stream.get("index")
        if not isinstance(stream_index, int):
            continue
        tags = stream.get("tags", {})
        language = None
        if isinstance(tags, dict):
            language = _normalize_language(tags.get("language"))
        results.append(
            SubtitleStream(
                stream_index=stream_index,
                subtitle_index=subtitle_index,
                language=language,
            )
        )
    return results


def _select_stream(streams: list[SubtitleStream], track: str | None) -> SubtitleStream:
    if not streams:
        raise RuntimeError("no subtitle streams found")

    if track is None or track.strip().lower() == "auto":
        for lang in _PREFERRED_ZH:
            for stream in streams:
                if stream.language == lang:
                    return stream
        for lang in _PREFERRED_EN:
            for stream in streams:
                if stream.language == lang:
                    return stream
        return streams[0]

    normalized = track.strip().lower()
    if normalized.isdigit():
        index = int(normalized)
        if index < 0 or index >= len(streams):
            raise RuntimeError(f"subtitle track index out of range: {index}")
        return streams[index]

    for stream in streams:
        if stream.language == _normalize_language(normalized):
            return stream

    raise RuntimeError(f"subtitle track language not found: {track}")


def _parse_timecode(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return (int(hours) * 3600) + (int(minutes) * 60) + int(seconds) + int(millis) / 1000.0


def _flatten_text(value: str) -> str:
    return " ".join(part.strip() for part in value.splitlines() if part.strip())


def extract_softsub_segments(video_path: str | Path, track: str | None = None) -> list[tuple[float, float, str]]:
    """Extract soft subtitle track into (start, end, text) segments."""
    streams = list_subtitle_streams(video_path)
    selected = _select_stream(streams, track)

    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(video_path),
        "-map",
        f"0:s:{selected.subtitle_index}",
        "-f",
        "srt",
        "-",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or "ffmpeg failed"
        raise RuntimeError(details)

    srt_text = (completed.stdout or "").strip()
    if not srt_text:
        raise RuntimeError("subtitle extraction produced empty output")

    segments: list[tuple[float, float, str]] = []
    for _idx, start, end, text in parse_srt_content(srt_text):
        flattened = _flatten_text(text)
        if not flattened:
            continue
        segments.append((_parse_timecode(start), _parse_timecode(end), flattened))
    return segments
