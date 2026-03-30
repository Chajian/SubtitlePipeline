"""SRT subtitle utilities."""

from __future__ import annotations

import re
from pathlib import Path


def format_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def segments_to_srt(segments: list[tuple[float, float, str]], filepath: str | Path) -> None:
    """Write (start, end, text) tuples to an SRT file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("w", encoding="utf-8") as file:
        for index, (start, end, text) in enumerate(segments, 1):
            file.write(f"{index}\n")
            file.write(f"{format_time(start)} --> {format_time(end)}\n")
            file.write(f"{text}\n\n")

    print(f"\033[32m[SRT]\033[0m 已写入: {filepath}")


def parse_srt_content(content: str) -> list[tuple[int, str, str, str]]:
    """Parse SRT content into (index, start, end, text) tuples."""
    pattern = re.compile(
        r"(\d+)\s*\n"
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n"
        r"((?:.*(?:\n|$))*?)"
        r"(?:\n|$)",
    )

    results: list[tuple[int, str, str, str]] = []
    for match in pattern.finditer(content):
        index = int(match.group(1))
        start = match.group(2)
        end = match.group(3)
        text = match.group(4).strip()
        results.append((index, start, end, text))
    return results


def parse_srt(filepath: str | Path) -> list[tuple[int, str, str, str]]:
    """Parse an SRT file into (index, start, end, text) tuples."""
    filepath = Path(filepath)
    content = filepath.read_text(encoding="utf-8")
    return parse_srt_content(content)


def segments_to_txt(segments: list[tuple[float, float, str]], filepath: str | Path) -> None:
    """Write segments to a time-stamped plain text file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("w", encoding="utf-8") as file:
        for start, end, text in segments:
            file.write(f"{format_time(start)} --> {format_time(end)}  {text}\n")


def merge_bilingual(
    cn_segments: list[tuple[float, float, str]],
    en_segments: list[tuple[float, float, str]],
    output_path: str | Path,
) -> None:
    """Merge Chinese and English segments into bilingual SRT."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for index, (cn_start, cn_end, cn_text) in enumerate(cn_segments, 1):
            best_en_text = ""
            best_distance = float("inf")
            for en_start, _en_end, en_text in en_segments:
                distance = abs(cn_start - en_start)
                if distance < best_distance:
                    best_distance = distance
                    best_en_text = en_text

            file.write(f"{index}\n")
            file.write(f"{format_time(cn_start)} --> {format_time(cn_end)}\n")
            file.write(f"{cn_text}\n{best_en_text}\n\n")

    print(f"\033[32m[SRT]\033[0m 双语字幕已写入: {output_path}")
