"""SRT 字幕文件的解析、格式化与合并"""

import re
from pathlib import Path


def format_time(seconds):
    """秒数 → SRT 时间格式 'HH:MM:SS,mmm'"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments, filepath):
    """
    将 [(start, end, text), ...] 写入 .srt 文件。

    Parameters
    ----------
    segments : list[tuple[float, float, str]]
    filepath : str | Path
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{text}\n\n")

    print(f"\033[32m[SRT]\033[0m 已写入: {filepath}")


def parse_srt(filepath):
    """
    解析 .srt 文件 → [(index, start, end, text), ...]

    Parameters
    ----------
    filepath : str | Path

    Returns
    -------
    list[tuple[int, str, str, str]]
        [(index, start_time_str, end_time_str, text), ...]
    """
    filepath = Path(filepath)
    content = filepath.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(\d+)\s*\n"
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n"
        r"((?:.*(?:\n|$))*?)"
        r"(?:\n|$)",
    )
    results = []
    for m in pattern.finditer(content):
        idx = int(m.group(1))
        start = m.group(2)
        end = m.group(3)
        text = m.group(4).strip()
        results.append((idx, start, end, text))
    return results


def merge_bilingual(cn_segments, en_segments, output_path):
    """
    合并中英文字幕为双语 .srt（中文在上、英文在下）。

    以中文字幕的时间轴为基准，为每条中文字幕找到时间上最接近的英文字幕。

    Parameters
    ----------
    cn_segments : list[tuple[float, float, str]]
    en_segments : list[tuple[float, float, str]]
    output_path : str | Path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 为每条中文字幕匹配最近的英文字幕
    en_idx = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for i, (cn_start, cn_end, cn_text) in enumerate(cn_segments, 1):
            # 找到时间最接近的英文字幕
            best_en = ""
            best_dist = float("inf")
            for j, (en_start, en_end, en_text) in enumerate(en_segments):
                dist = abs(cn_start - en_start)
                if dist < best_dist:
                    best_dist = dist
                    best_en = en_text

            f.write(f"{i}\n")
            f.write(f"{format_time(cn_start)} --> {format_time(cn_end)}\n")
            f.write(f"{cn_text}\n{best_en}\n\n")

    print(f"\033[32m[SRT]\033[0m 双语字幕已写入: {output_path}")
