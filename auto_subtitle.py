#!/usr/bin/env python3
"""CLI entrypoint for subtitle generation and optional hard-sub burn-in."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from subtitle.env_loader import bootstrap_ai_review_env

bootstrap_ai_review_env(Path(__file__).resolve().parent)

try:
    from opencc import OpenCC  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    OpenCC = None  # type: ignore[assignment]


def _convert_zh_segments(
    segments: list[tuple[float, float, str]],
    zh_script: str,
) -> list[tuple[float, float, str]]:
    """Convert Chinese subtitle text between simplified/traditional when requested."""
    if zh_script == "raw":
        return segments

    convert_mode = {"simplified": "t2s", "traditional": "s2t"}[zh_script]
    if OpenCC is None:
        print(
            "\033[33m[warn]\033[0m OpenCC is not installed; "
            "Chinese script conversion was skipped "
            "(install: .\\.venv\\Scripts\\pip.exe install opencc-python-reimplemented)."
        )
        return segments

    converter = OpenCC(convert_mode)
    return [(start, end, converter.convert(text)) for start, end, text in segments]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Chinese/English subtitles and optionally burn hard subtitles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python auto_subtitle.py input.mp4\n"
            "  python auto_subtitle.py input.mp4 --model small --no-burn\n"
            "  python auto_subtitle.py input.mp4 --model-source auto --mirror-endpoint https://hf-mirror.com\n"
            "  python auto_subtitle.py input.mp4 --model-source local --model-dir ./models\n"
            "  python auto_subtitle.py input.mp4 --source-language zh-CN --zh-script simplified\n"
            "  python auto_subtitle.py input.mp4 --ai-review on --ai-review-provider openai --ai-review-model gpt-4.1-mini\n"
            "  python auto_subtitle.py input.mp4 --ai-review on --ai-review-provider siliconflow --ai-review-model Qwen/Qwen2.5-72B-Instruct\n"
            "  python auto_subtitle.py input.mp4 --burn-only output/input.bilingual.srt\n"
        ),
    )
    parser.add_argument("video", help="Input video path")
    parser.add_argument(
        "--model",
        default="medium",
        help="Whisper model size (tiny/base/small/medium/large-v3)",
    )
    parser.add_argument(
        "--source-language",
        default="zh",
        help="Source language (default: zh, aliases: zh-CN/zh-Hans/cn/chinese)",
    )
    parser.add_argument(
        "--zh-script",
        default="simplified",
        choices=["simplified", "traditional", "raw"],
        help="Chinese subtitle script (default: simplified)",
    )
    parser.add_argument(
        "--model-source",
        default="auto",
        choices=["auto", "official", "mirror", "local"],
        help="Model source strategy (default: auto)",
    )
    parser.add_argument(
        "--model-dir",
        default=None,
        help="Model directory (local model dir or cache dir)",
    )
    parser.add_argument(
        "--mirror-endpoint",
        default=None,
        help="Mirror endpoint, e.g. https://hf-mirror.com",
    )
    parser.add_argument(
        "--output",
        default="output",
        help="Output directory (default: output)",
    )
    parser.add_argument(
        "--ai-review",
        default=os.getenv("AI_REVIEW_MODE", "auto"),
        choices=["auto", "on", "off"],
        help="Review bilingual subtitles with the selected AI provider (default: auto)",
    )
    parser.add_argument(
        "--ai-review-provider",
        default=os.getenv("AI_REVIEW_PROVIDER", "codex"),
        choices=["codex", "openai", "siliconflow"],
        help="AI review provider (default: codex)",
    )
    parser.add_argument(
        "--ai-review-model",
        default=os.getenv("AI_REVIEW_MODEL"),
        help="Optional model override for subtitle review",
    )
    parser.add_argument(
        "--ai-review-base-url",
        default=os.getenv("AI_REVIEW_BASE_URL"),
        help="Optional OpenAI-compatible base URL override for subtitle review",
    )
    parser.add_argument(
        "--no-burn",
        action="store_true",
        help="Generate SRT only and skip hard-sub burn",
    )
    parser.add_argument(
        "--burn-only",
        metavar="SRT",
        help="Skip ASR/translation and burn with existing SRT",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    video = Path(args.video)
    if not video.exists():
        print(f"\033[31m[error]\033[0m video not found: {video}")
        sys.exit(1)

    from subtitle.embed import burn_subtitles, check_ffmpeg

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.burn_only:
        srt = Path(args.burn_only)
        if not srt.exists():
            print(f"\033[31m[error]\033[0m SRT not found: {srt}")
            sys.exit(1)
        check_ffmpeg()
        output_video = output_dir / f"{video.stem}.hardsub.mp4"
        print("\n\033[1;36m> Burn hard subtitles\033[0m")
        burn_subtitles(str(video), str(srt), str(output_video))
        print(f"\n\033[1;32mDone: {output_video}\033[0m")
        return

    import config

    config.MODEL_SIZE = args.model
    config.MODEL_SOURCE = args.model_source
    config.MODEL_DIR = args.model_dir
    config.MODEL_MIRROR_ENDPOINT = args.mirror_endpoint
    config.CHINESE_SCRIPT = args.zh_script
    config.AI_REVIEW_MODE = args.ai_review
    config.AI_REVIEW_PROVIDER = args.ai_review_provider
    config.AI_REVIEW_MODEL = args.ai_review_model
    config.AI_REVIEW_BASE_URL = args.ai_review_base_url

    from subtitle.ai_review import (
        AIReviewSettings,
        maybe_review_bilingual_srt,
        maybe_review_text_segments,
        translate_text_segments_to_english,
    )
    from subtitle.srt import merge_bilingual, segments_to_srt
    from subtitle.transcribe import preflight_model_access, transcribe_speech, translate_to_english

    stem = video.stem
    total_steps = 6 if args.ai_review != "off" else 4

    if not args.no_burn:
        check_ffmpeg()

    print()
    print("\033[1;35m" + "=" * 50 + "\033[0m")
    print("\033[1;35m  Subtitle Pipeline\033[0m")
    print(f"\033[1;35m  Video: {video.name}\033[0m")
    print(f"\033[1;35m  Source language: {args.source_language}\033[0m")
    print(f"\033[1;35m  Chinese script: {args.zh_script}\033[0m")
    print(f"\033[1;35m  Model: {args.model}\033[0m")
    print(f"\033[1;35m  Model source: {args.model_source}\033[0m")
    if args.model_dir:
        print(f"\033[1;35m  Model dir: {args.model_dir}\033[0m")
    if args.mirror_endpoint:
        print(f"\033[1;35m  Mirror endpoint: {args.mirror_endpoint}\033[0m")
    print(f"\033[1;35m  AI review: {args.ai_review}\033[0m")
    print(f"\033[1;35m  AI review provider: {args.ai_review_provider}\033[0m")
    if args.ai_review_model:
        print(f"\033[1;35m  AI review model: {args.ai_review_model}\033[0m")
    if args.ai_review_base_url:
        print(f"\033[1;35m  AI review base URL: {args.ai_review_base_url}\033[0m")
    print("\033[1;35m" + "=" * 50 + "\033[0m")

    try:
        print("\n\033[1;36m> Preflight model/network\033[0m")
        preflight_model_access()

        print(f"\n\033[1;36m> Step 1/{total_steps}: transcribe source speech\033[0m")
        cn_segments = transcribe_speech(str(video), source_language=args.source_language)
        source_lang = args.source_language.strip().lower().replace("_", "-")
        is_zh_source = source_lang in {"zh", "zh-cn", "zh-hans", "cn", "chinese"} or source_lang.startswith("zh-")
        if is_zh_source and args.zh_script != "raw":
            print(f"\033[36m[text]\033[0m Convert Chinese script -> {args.zh_script}")
            cn_segments = _convert_zh_segments(cn_segments, args.zh_script)
        cn_srt = output_dir / f"{stem}.cn.srt"
        segments_to_srt(cn_segments, cn_srt)
        reviewed_cn_srt = output_dir / f"{stem}.cn.reviewed.srt"
        active_cn_segments = cn_segments
        ai_cn_review_applied = False

        review_settings = AIReviewSettings(
            mode=config.AI_REVIEW_MODE,
            provider=config.AI_REVIEW_PROVIDER,
            command=config.AI_REVIEW_COMMAND,
            model=config.AI_REVIEW_MODEL,
            base_url=config.AI_REVIEW_BASE_URL,
            max_blocks_per_chunk=config.AI_REVIEW_MAX_BLOCKS_PER_CHUNK,
            max_chars_per_chunk=config.AI_REVIEW_MAX_CHARS_PER_CHUNK,
            timeout_seconds=config.AI_REVIEW_TIMEOUT_SECONDS,
            max_attempts=config.AI_REVIEW_MAX_ATTEMPTS,
        )

        if args.ai_review != "off":
            print(f"\n\033[1;36m> Step 2/{total_steps}: review Chinese subtitles\033[0m")
            active_cn_segments, ai_cn_review_applied = maybe_review_text_segments(
                cn_segments,
                reviewed_cn_srt,
                review_settings,
            )

        if args.ai_review != "off":
            print(f"\n\033[1;36m> Step 3/{total_steps}: translate reviewed Chinese subtitles to english\033[0m")
            try:
                en_segments = translate_text_segments_to_english(active_cn_segments, review_settings)
            except Exception as exc:  # noqa: BLE001
                if args.ai_review in {"on", "auto"}:
                    print(
                        "\033[33m[AI]\033[0m Reviewed-text English translation failed; "
                        "falling back to Whisper audio translation."
                    )
                    print(f"\033[33m[AI]\033[0m Reason: {exc}")
                    en_segments = translate_to_english(str(video), source_language=args.source_language)
                else:
                    raise
        else:
            print(f"\n\033[1;36m> Step 2/{total_steps}: translate to english\033[0m")
            en_segments = translate_to_english(str(video), source_language=args.source_language)
        en_srt = output_dir / f"{stem}.en.srt"
        segments_to_srt(en_segments, en_srt)

        merge_step = 4 if args.ai_review != "off" else 3
        print(f"\n\033[1;36m> Step {merge_step}/{total_steps}: merge bilingual subtitles\033[0m")
        bilingual_srt = output_dir / f"{stem}.bilingual.srt"
        merge_bilingual(active_cn_segments, en_segments, bilingual_srt)
        reviewed_srt = output_dir / f"{stem}.bilingual.reviewed.srt"
        active_bilingual_srt = bilingual_srt
        ai_bilingual_review_applied = False

        if args.ai_review != "off":
            print(f"\n\033[1;36m> Step 5/{total_steps}: optional bilingual subtitle review\033[0m")
            active_bilingual_srt, ai_bilingual_review_applied = maybe_review_bilingual_srt(
                bilingual_srt,
                reviewed_srt,
                review_settings,
            )

        burn_step = total_steps

        output_video = output_dir / f"{stem}.hardsub.mp4"
        if args.no_burn:
            print(f"\n\033[1;33m> Step {burn_step}/{total_steps}: skip burn (--no-burn)\033[0m")
        else:
            print(f"\n\033[1;36m> Step {burn_step}/{total_steps}: burn hard subtitles\033[0m")
            burn_subtitles(str(video), str(active_bilingual_srt), str(output_video))

    except KeyboardInterrupt:
        print("\n\033[31m[interrupted]\033[0m cancelled by user")
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        print("\n\033[31m[error]\033[0m subtitle generation failed")
        print(f"  {exc}")
        sys.exit(1)

    print()
    print("\033[1;32m" + "=" * 50 + "\033[0m")
    print("\033[1;32m  Completed\033[0m")
    print(f"\033[1;32m  Output dir: {output_dir.resolve()}\033[0m")
    print(f"  Chinese SRT:   {cn_srt}")
    if args.ai_review != "off":
        if ai_cn_review_applied:
            print(f"  Reviewed CN:   {reviewed_cn_srt}")
        else:
            print("  Reviewed CN:   skipped (using raw Chinese SRT)")
    print(f"  English SRT:   {en_srt}")
    print(f"  Bilingual SRT: {bilingual_srt}")
    if args.ai_review != "off":
        if ai_bilingual_review_applied:
            print(f"  Reviewed SRT:  {active_bilingual_srt}")
        else:
            print("  Reviewed SRT:  skipped (using raw bilingual SRT)")
    if not args.no_burn:
        print(f"  Burn source:   {active_bilingual_srt}")
        print(f"  Hard-sub video: {output_video}")
    print("\033[1;32m" + "=" * 50 + "\033[0m")


if __name__ == "__main__":
    main()
