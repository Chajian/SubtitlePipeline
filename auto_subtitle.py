#!/usr/bin/env python3
"""
OBS 视频自动生成中英文双语字幕

用法:
    python auto_subtitle.py <video> [options]

示例:
    python auto_subtitle.py my_video.mp4
    python auto_subtitle.py my_video.mp4 --model medium --no-burn
    python auto_subtitle.py my_video.mp4 --burn-only output/my_video.bilingual.srt
"""

import argparse
import os
import sys
from pathlib import Path

# Windows 下强制 UTF-8 输出，避免 GBK 编码错误
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 将项目根目录加入 sys.path，确保可以 import config
sys.path.insert(0, str(Path(__file__).resolve().parent))


def parse_args():
    parser = argparse.ArgumentParser(
        description="OBS 视频自动生成中英文双语字幕",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python auto_subtitle.py my_video.mp4\n"
               "  python auto_subtitle.py my_video.mp4 --model medium --no-burn\n"
               "  python auto_subtitle.py my_video.mp4 --burn-only output/my_video.bilingual.srt\n",
    )
    parser.add_argument("video", help="输入视频文件路径")
    parser.add_argument("--model", default="large-v3",
                        help="Whisper 模型大小 (默认: large-v3)")
    parser.add_argument("--output", default="output",
                        help="输出目录 (默认: output)")
    parser.add_argument("--no-burn", action="store_true",
                        help="仅生成 SRT，不烧录硬字幕")
    parser.add_argument("--burn-only", metavar="SRT",
                        help="跳过识别/翻译，直接用指定 SRT 烧录硬字幕")
    return parser.parse_args()


def main():
    args = parse_args()

    video = Path(args.video)
    if not video.exists():
        print(f"\033[31m[错误]\033[0m 视频文件不存在: {video}")
        sys.exit(1)

    # 延迟导入，避免 --help 时要求依赖已安装
    from subtitle.embed import burn_subtitles, check_ffmpeg

    # ── burn-only 模式：跳过识别，直接烧录 ────────────────────
    if args.burn_only:
        srt = Path(args.burn_only)
        if not srt.exists():
            print(f"\033[31m[错误]\033[0m SRT 文件不存在: {srt}")
            sys.exit(1)
        check_ffmpeg()
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_video = output_dir / f"{video.stem}.硬字幕.mp4"
        print()
        print("\033[1;36m▶ 烧录硬字幕\033[0m")
        burn_subtitles(str(video), str(srt), str(output_video))
        print()
        print(f"\033[1;32m  完成: {output_video}\033[0m")
        return

    import config
    from subtitle.transcribe import transcribe_chinese, translate_to_english
    from subtitle.srt import segments_to_srt, merge_bilingual

    # 动态覆盖模型大小
    config.MODEL_SIZE = args.model

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = video.stem  # 无后缀文件名

    # 如果需要烧录，提前检查 FFmpeg
    if not args.no_burn:
        check_ffmpeg()

    print()
    print("\033[1;35m" + "=" * 50 + "\033[0m")
    print(f"\033[1;35m  自动双语字幕生成\033[0m")
    print(f"\033[1;35m  视频: {video.name}\033[0m")
    print("\033[1;35m" + "=" * 50 + "\033[0m")
    print()

    # ── Step 1: 识别中文 ──────────────────────────────────────
    print("\033[1;36m▶ Step 1/4: 识别中文语音\033[0m")
    cn_segments = transcribe_chinese(str(video))
    cn_srt = output_dir / f"{stem}.cn.srt"
    segments_to_srt(cn_segments, cn_srt)
    print()

    # ── Step 2: 翻译英文 ──────────────────────────────────────
    print("\033[1;36m▶ Step 2/4: 翻译为英文\033[0m")
    en_segments = translate_to_english(str(video))
    en_srt = output_dir / f"{stem}.en.srt"
    segments_to_srt(en_segments, en_srt)
    print()

    # ── Step 3: 合并双语字幕 ──────────────────────────────────
    print("\033[1;36m▶ Step 3/4: 合并双语字幕\033[0m")
    bilingual_srt = output_dir / f"{stem}.bilingual.srt"
    merge_bilingual(cn_segments, en_segments, bilingual_srt)
    print()

    # ── Step 4: 烧录硬字幕 ────────────────────────────────────
    if args.no_burn:
        print("\033[1;33m▶ Step 4/4: 跳过烧录（--no-burn）\033[0m")
    else:
        print("\033[1;36m▶ Step 4/4: 烧录硬字幕\033[0m")
        output_video = output_dir / f"{stem}.硬字幕.mp4"
        burn_subtitles(str(video), str(bilingual_srt), str(output_video))
    print()

    # ── 完成 ──────────────────────────────────────────────────
    print("\033[1;32m" + "=" * 50 + "\033[0m")
    print(f"\033[1;32m  全部完成！\033[0m")
    print(f"\033[1;32m  输出目录: {output_dir.resolve()}\033[0m")
    print()
    print(f"  中文字幕:   {cn_srt}")
    print(f"  英文字幕:   {en_srt}")
    print(f"  双语字幕:   {bilingual_srt}")
    if not args.no_burn:
        print(f"  硬字幕视频: {output_video}")
    print("\033[1;32m" + "=" * 50 + "\033[0m")


if __name__ == "__main__":
    main()
