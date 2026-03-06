"""FFmpeg 硬字幕烧录与软字幕封装"""

import shutil
import subprocess
import sys
from pathlib import Path

from config import SUBTITLE_STYLE


def check_ffmpeg():
    """检测 FFmpeg 是否可用，不可用则退出"""
    if shutil.which("ffmpeg") is None:
        print("\033[31m[错误]\033[0m 未找到 FFmpeg，请先安装并加入 PATH")
        print("  下载地址: https://ffmpeg.org/download.html")
        sys.exit(1)


def _build_ass_style(style=None):
    """
    将样式字典转为 FFmpeg subtitles 滤镜的 force_style 参数。
    例: "FontName=Microsoft YaHei,FontSize=20,..."
    """
    s = style or SUBTITLE_STYLE
    return ",".join(f"{k}={v}" for k, v in s.items())


def burn_subtitles(video_path, srt_path, output_path, style=None):
    """
    使用 FFmpeg subtitles 滤镜将 SRT 烧录为硬字幕。

    Parameters
    ----------
    video_path : str | Path
    srt_path : str | Path
    output_path : str | Path
    style : dict | None  自定义 ASS 样式
    """
    check_ffmpeg()

    video_path = Path(video_path)
    srt_path = Path(srt_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # FFmpeg subtitles 滤镜需要用 / 或 \\\\ 作路径分隔符
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")

    force_style = _build_ass_style(style)
    vf = f"subtitles='{srt_escaped}':force_style='{force_style}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", vf,
        "-c:a", "copy",
        str(output_path),
    ]

    print(f"\033[36m[烧录]\033[0m 硬字幕烧录中...")
    print(f"  输入: {video_path}")
    print(f"  字幕: {srt_path}")
    print(f"  输出: {output_path}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\033[31m[错误]\033[0m FFmpeg 烧录失败:")
        print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
        sys.exit(1)

    print(f"\033[32m[烧录]\033[0m 完成: {output_path}")


def mux_subtitles(video_path, srt_path, output_path):
    """
    将 SRT 作为软字幕封装到 MKV 容器。

    Parameters
    ----------
    video_path : str | Path
    srt_path : str | Path
    output_path : str | Path  应以 .mkv 结尾
    """
    check_ffmpeg()

    video_path = Path(video_path)
    srt_path = Path(srt_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(srt_path),
        "-c", "copy",
        "-c:s", "srt",
        str(output_path),
    ]

    print(f"\033[36m[封装]\033[0m 软字幕封装中...")
    print(f"  输入: {video_path}")
    print(f"  字幕: {srt_path}")
    print(f"  输出: {output_path}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\033[31m[错误]\033[0m FFmpeg 封装失败:")
        print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
        sys.exit(1)

    print(f"\033[32m[封装]\033[0m 完成: {output_path}")
