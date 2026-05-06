#!/usr/bin/env python3
"""CLI entrypoint for subtitle generation and optional hard-sub burn-in."""

from __future__ import annotations

import argparse
import json
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


def _progress_artifact(path: str | Path, kind: str) -> dict[str, str]:
    artifact_path = Path(path)
    return {
        "name": artifact_path.name,
        "kind": kind,
        "status": "ready",
    }


def _write_web_progress(
    progress_path: str | Path | None,
    *,
    primary_status: str,
    enhancement_status: str,
    current_stage: str,
    artifacts: list[dict[str, str]] | None = None,
    primary_error_text: str | None = None,
    enhancement_error_text: str | None = None,
) -> None:
    if not progress_path:
        return

    payload = {
        "primary_status": primary_status,
        "enhancement_status": enhancement_status,
        "current_stage": current_stage,
        "artifacts": artifacts or [],
        "primary_error_text": primary_error_text,
        "enhancement_error_text": enhancement_error_text,
    }
    target = Path(progress_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
            "  python auto_subtitle.py input.mp4 --merge-mode ai --subtitle-track auto --output-format both --text-only\n"
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
        "--text-only",
        action="store_true",
        help="Skip hard-sub burn and generate text outputs only",
    )
    parser.add_argument(
        "--subtitle-track",
        default=None,
        help="Soft subtitle track to merge (auto / index / language tag)",
    )
    parser.add_argument(
        "--merge-mode",
        choices=["ai", "prefer-srt", "prefer-asr"],
        default=None,
        help="Merge ASR with soft subtitles (default: disabled)",
    )
    parser.add_argument(
        "--output-format",
        choices=["srt", "txt", "both"],
        default="both",
        help="Merged text output format (default: both)",
    )
    parser.add_argument(
        "--burn-only",
        metavar="SRT",
        help="Skip ASR/translation and burn with existing SRT",
    )
    parser.add_argument(
        "--web-progress-file",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--retry-enhancement",
        action="store_true",
        help=argparse.SUPPRESS,
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
    if args.text_only:
        args.no_burn = True

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
        load_text_srt,
        maybe_review_bilingual_srt,
        maybe_review_text_segments,
        merge_aligned_blocks,
        preflight_ai_review_access,
        text_blocks_to_segments,
        translate_text_segments_to_english,
    )
    from subtitle.merge import align_segments, merge_blocks_prefer_asr, merge_blocks_prefer_srt
    from subtitle.softsub import extract_softsub_segments
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
    if args.merge_mode:
        print(f"\033[1;35m  Merge mode: {args.merge_mode}\033[0m")
        if args.subtitle_track:
            print(f"\033[1;35m  Subtitle track: {args.subtitle_track}\033[0m")
        print(f"\033[1;35m  Output format: {args.output_format}\033[0m")
    print("\033[1;35m" + "=" * 50 + "\033[0m")

    try:
        print("\n\033[1;36m> Preflight model/network\033[0m")
        preflight_model_access()

        if args.ai_review != "off":
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
            print("\033[36m[AI]\033[0m Preflight AI review connectivity")
            preflight_ai_review_access(review_settings)

        if args.retry_enhancement:
            if args.ai_review == "off":
                raise ValueError("--retry-enhancement requires AI review to be enabled")

            cn_srt = output_dir / f"{stem}.cn.srt"
            en_srt = output_dir / f"{stem}.en.srt"
            bilingual_srt = output_dir / f"{stem}.bilingual.srt"
            reviewed_cn_srt = output_dir / f"{stem}.cn.reviewed.srt"
            reviewed_srt = output_dir / f"{stem}.bilingual.reviewed.srt"

            if not cn_srt.exists():
                raise ValueError(f"draft Chinese SRT not found: {cn_srt}")

            cn_segments = text_blocks_to_segments(load_text_srt(cn_srt))
            draft_artifacts = [_progress_artifact(cn_srt, "draft_subtitle")]
            if en_srt.exists():
                draft_artifacts.append(_progress_artifact(en_srt, "draft_translation"))
            if bilingual_srt.exists():
                draft_artifacts.append(_progress_artifact(bilingual_srt, "draft_bilingual_subtitle"))

            _write_web_progress(
                args.web_progress_file,
                primary_status="draft_ready",
                enhancement_status="reviewing",
                current_stage="reviewing",
                artifacts=draft_artifacts,
            )

            active_cn_segments = cn_segments
            ai_cn_review_applied = False
            ai_bilingual_review_applied = False
            enhancement_failed = False
            enhancement_error_text: str | None = None

            print("\n\033[1;36m> Retry enhancement: review Chinese subtitles\033[0m")
            try:
                active_cn_segments, ai_cn_review_applied = maybe_review_text_segments(
                    cn_segments,
                    reviewed_cn_srt,
                    review_settings,
                )
            except Exception as exc:  # noqa: BLE001
                enhancement_failed = True
                enhancement_error_text = str(exc)
                active_cn_segments = cn_segments
                print("\033[33m[AI]\033[0m Chinese subtitle review failed; using draft subtitles.")
                print(f"\033[33m[AI]\033[0m Reason: {exc}")

            active_bilingual_srt = bilingual_srt
            if not enhancement_failed:
                print("\n\033[1;36m> Retry enhancement: translate reviewed Chinese subtitles to english\033[0m")
                try:
                    en_segments = translate_text_segments_to_english(active_cn_segments, review_settings)
                    segments_to_srt(en_segments, en_srt)
                    if not any(item["name"] == en_srt.name for item in draft_artifacts):
                        draft_artifacts.append(_progress_artifact(en_srt, "draft_translation"))
                    merge_bilingual(active_cn_segments, en_segments, bilingual_srt)
                    if not any(item["name"] == bilingual_srt.name for item in draft_artifacts):
                        draft_artifacts.append(_progress_artifact(bilingual_srt, "draft_bilingual_subtitle"))
                except Exception as exc:  # noqa: BLE001
                    enhancement_failed = True
                    enhancement_error_text = str(exc)
                    print("\033[33m[AI]\033[0m Reviewed-text English translation failed; keeping draft bilingual subtitles.")
                    print(f"\033[33m[AI]\033[0m Reason: {exc}")

            if not enhancement_failed:
                print("\n\033[1;36m> Retry enhancement: optional bilingual subtitle review\033[0m")
                try:
                    active_bilingual_srt, ai_bilingual_review_applied = maybe_review_bilingual_srt(
                        bilingual_srt,
                        reviewed_srt,
                        review_settings,
                    )
                except Exception as exc:  # noqa: BLE001
                    enhancement_failed = True
                    enhancement_error_text = str(exc)
                    active_bilingual_srt = bilingual_srt
                    print("\033[33m[AI]\033[0m Bilingual subtitle review failed; keeping draft bilingual subtitles.")
                    print(f"\033[33m[AI]\033[0m Reason: {exc}")

            final_artifacts = list(draft_artifacts)
            if ai_cn_review_applied:
                final_artifacts.append(_progress_artifact(reviewed_cn_srt, "reviewed_subtitle"))
            if ai_bilingual_review_applied:
                final_artifacts.append(_progress_artifact(active_bilingual_srt, "reviewed_bilingual_subtitle"))

            if enhancement_failed:
                _write_web_progress(
                    args.web_progress_file,
                    primary_status="draft_ready",
                    enhancement_status="failed",
                    current_stage="draft_ready",
                    artifacts=final_artifacts,
                    enhancement_error_text=enhancement_error_text,
                )
            else:
                _write_web_progress(
                    args.web_progress_file,
                    primary_status="completed",
                    enhancement_status="succeeded",
                    current_stage="completed",
                    artifacts=final_artifacts,
                )
            return

        if args.merge_mode:
            if args.merge_mode == "ai" and args.ai_review == "off":
                raise ValueError("--merge-mode ai requires --ai-review on or auto")

            print("\n\033[1;36m> Step 1/3: transcribe source speech\033[0m")
            asr_segments = transcribe_speech(str(video), source_language=args.source_language)

            print("\n\033[1;36m> Step 2/3: extract soft subtitle track\033[0m")
            try:
                srt_segments = extract_softsub_segments(
                    str(video),
                    args.subtitle_track,
                    source_language=args.source_language,
                )
            except Exception as exc:  # noqa: BLE001
                print("\033[33m[warn]\033[0m Soft subtitles not found; fallback to ASR only.")
                print(f"\033[33m[warn]\033[0m Reason: {exc}")
                srt_segments = []

            print("\n\033[1;36m> Step 3/3: merge ASR and soft subtitles\033[0m")
            if not srt_segments:
                merged_segments = asr_segments
            else:
                aligned = align_segments(asr_segments, srt_segments)
                merged_segments: list[tuple[float, float, str]]
                if args.merge_mode == "ai":
                    try:
                        merged_segments = merge_aligned_blocks(aligned, review_settings)
                    except Exception as exc:  # noqa: BLE001
                        if args.ai_review == "auto":
                            print(
                                "\033[33m[AI]\033[0m AI merge skipped; "
                                "falling back to soft subtitles."
                            )
                            print(f"\033[33m[AI]\033[0m Reason: {exc}")
                            merged_segments = merge_blocks_prefer_srt(aligned)
                        else:
                            raise
                elif args.merge_mode == "prefer-asr":
                    merged_segments = merge_blocks_prefer_asr(aligned)
                else:
                    merged_segments = merge_blocks_prefer_srt(aligned)

            source_lang = args.source_language.strip().lower().replace("_", "-")
            is_zh_source = source_lang in {"zh", "zh-cn", "zh-hans", "cn", "chinese"} or source_lang.startswith("zh-")
            if is_zh_source and args.zh_script != "raw":
                print(f"\033[36m[text]\033[0m Convert Chinese script -> {args.zh_script}")
                merged_segments = _convert_zh_segments(merged_segments, args.zh_script)

            merged_srt = output_dir / f"{stem}.merged.srt"
            merged_txt = output_dir / f"{stem}.merged.txt"
            need_srt = args.output_format in {"srt", "both"} or not args.no_burn
            if need_srt:
                segments_to_srt(merged_segments, merged_srt)
            if args.output_format in {"txt", "both"}:
                from subtitle.srt import segments_to_txt

                segments_to_txt(merged_segments, merged_txt)

            if not args.no_burn:
                print("\n\033[1;36m> Burn merged subtitles\033[0m")
                output_video = output_dir / f"{stem}.merged.hardsub.mp4"
                burn_subtitles(str(video), str(merged_srt), str(output_video))

            print()
            print("\033[1;32m" + "=" * 50 + "\033[0m")
            print("\033[1;32m  Completed (Merged Text)\033[0m")
            print(f"\033[1;32m  Output dir: {output_dir.resolve()}\033[0m")
            if args.output_format in {"srt", "both"}:
                print(f"  Merged SRT:  {merged_srt}")
            if args.output_format in {"txt", "both"}:
                print(f"  Merged TXT:  {merged_txt}")
            if not args.no_burn:
                print(f"  Hard-sub video: {output_video}")
            print("\033[1;32m" + "=" * 50 + "\033[0m")
            return

        print(f"\n\033[1;36m> Step 1/{total_steps}: transcribe source speech\033[0m")
        _write_web_progress(
            args.web_progress_file,
            primary_status="transcribing",
            enhancement_status="pending",
            current_stage="transcribing",
        )
        cn_segments = transcribe_speech(str(video), source_language=args.source_language)
        source_lang = args.source_language.strip().lower().replace("_", "-")
        is_zh_source = source_lang in {"zh", "zh-cn", "zh-hans", "cn", "chinese"} or source_lang.startswith("zh-")
        if is_zh_source and args.zh_script != "raw":
            print(f"\033[36m[text]\033[0m Convert Chinese script -> {args.zh_script}")
            cn_segments = _convert_zh_segments(cn_segments, args.zh_script)
        cn_srt = output_dir / f"{stem}.cn.srt"
        segments_to_srt(cn_segments, cn_srt)
        draft_artifacts = [_progress_artifact(cn_srt, "draft_subtitle")]
        if not cn_segments:
            print("\033[33m[warn]\033[0m No speech segments were detected; downstream subtitle steps were skipped.")
            en_srt = output_dir / f"{stem}.en.srt"
            bilingual_srt = output_dir / f"{stem}.bilingual.srt"
            segments_to_srt([], en_srt)
            segments_to_srt([], bilingual_srt)
            draft_artifacts.extend(
                [
                    _progress_artifact(en_srt, "draft_translation"),
                    _progress_artifact(bilingual_srt, "draft_bilingual_subtitle"),
                ]
            )
            _write_web_progress(
                args.web_progress_file,
                primary_status="completed",
                enhancement_status="skipped",
                current_stage="completed",
                artifacts=draft_artifacts,
            )

            print()
            print("\033[1;32m" + "=" * 50 + "\033[0m")
            print("\033[1;32m  Completed (No Speech Detected)\033[0m")
            print(f"\033[1;32m  Output dir: {output_dir.resolve()}\033[0m")
            print(f"  Chinese SRT:   {cn_srt}")
            if args.ai_review != "off":
                print("  Reviewed CN:   skipped (no subtitle blocks to review)")
            print(f"  English SRT:   {en_srt}")
            print(f"  Bilingual SRT: {bilingual_srt}")
            if args.ai_review != "off":
                print("  Reviewed SRT:  skipped (no subtitle blocks to review)")
            if not args.no_burn:
                print("  Burn source:   skipped (no subtitle blocks to burn)")
                print("  Hard-sub video: skipped")
            print("\033[1;32m" + "=" * 50 + "\033[0m")
            return
        reviewed_cn_srt = output_dir / f"{stem}.cn.reviewed.srt"
        active_cn_segments = cn_segments
        ai_cn_review_applied = False
        enhancement_failed = False
        enhancement_error_text: str | None = None

        if args.ai_review != "off":
            print(f"\n\033[1;36m> Step 2/{total_steps}: review Chinese subtitles\033[0m")
            _write_web_progress(
                args.web_progress_file,
                primary_status="draft_ready",
                enhancement_status="reviewing",
                current_stage="reviewing",
                artifacts=draft_artifacts,
            )
            try:
                active_cn_segments, ai_cn_review_applied = maybe_review_text_segments(
                    cn_segments,
                    reviewed_cn_srt,
                    review_settings,
                )
            except Exception as exc:  # noqa: BLE001
                enhancement_failed = True
                enhancement_error_text = str(exc)
                active_cn_segments = cn_segments
                print("\033[33m[AI]\033[0m Chinese subtitle review failed; using draft subtitles.")
                print(f"\033[33m[AI]\033[0m Reason: {exc}")

        if args.ai_review != "off":
            print(f"\n\033[1;36m> Step 3/{total_steps}: translate reviewed Chinese subtitles to english\033[0m")
            if enhancement_failed:
                en_segments = translate_to_english(str(video), source_language=args.source_language)
            else:
                try:
                    en_segments = translate_text_segments_to_english(active_cn_segments, review_settings)
                except Exception as exc:  # noqa: BLE001
                    enhancement_failed = True
                    enhancement_error_text = str(exc)
                    print(
                        "\033[33m[AI]\033[0m Reviewed-text English translation failed; "
                        "falling back to Whisper audio translation."
                    )
                    print(f"\033[33m[AI]\033[0m Reason: {exc}")
                    active_cn_segments = cn_segments
                    en_segments = translate_to_english(str(video), source_language=args.source_language)
        else:
            print(f"\n\033[1;36m> Step 2/{total_steps}: translate to english\033[0m")
            en_segments = translate_to_english(str(video), source_language=args.source_language)
        en_srt = output_dir / f"{stem}.en.srt"
        segments_to_srt(en_segments, en_srt)
        draft_artifacts.append(_progress_artifact(en_srt, "draft_translation"))

        merge_step = 4 if args.ai_review != "off" else 3
        print(f"\n\033[1;36m> Step {merge_step}/{total_steps}: merge bilingual subtitles\033[0m")
        bilingual_srt = output_dir / f"{stem}.bilingual.srt"
        merge_bilingual(active_cn_segments, en_segments, bilingual_srt)
        draft_artifacts.append(_progress_artifact(bilingual_srt, "draft_bilingual_subtitle"))
        reviewed_srt = output_dir / f"{stem}.bilingual.reviewed.srt"
        active_bilingual_srt = bilingual_srt
        ai_bilingual_review_applied = False

        if args.ai_review != "off":
            print(f"\n\033[1;36m> Step 5/{total_steps}: optional bilingual subtitle review\033[0m")
            _write_web_progress(
                args.web_progress_file,
                primary_status="draft_ready",
                enhancement_status="reviewing" if not enhancement_failed else "failed",
                current_stage="reviewing" if not enhancement_failed else "draft_ready",
                artifacts=draft_artifacts,
                enhancement_error_text=enhancement_error_text,
            )
            if not enhancement_failed:
                try:
                    active_bilingual_srt, ai_bilingual_review_applied = maybe_review_bilingual_srt(
                        bilingual_srt,
                        reviewed_srt,
                        review_settings,
                    )
                except Exception as exc:  # noqa: BLE001
                    enhancement_failed = True
                    enhancement_error_text = str(exc)
                    active_bilingual_srt = bilingual_srt
                    print("\033[33m[AI]\033[0m Bilingual subtitle review failed; keeping draft bilingual subtitles.")
                    print(f"\033[33m[AI]\033[0m Reason: {exc}")

        burn_step = total_steps

        output_video = output_dir / f"{stem}.hardsub.mp4"
        if args.no_burn:
            print(f"\n\033[1;33m> Step {burn_step}/{total_steps}: skip burn (--no-burn)\033[0m")
        else:
            print(f"\n\033[1;36m> Step {burn_step}/{total_steps}: burn hard subtitles\033[0m")
            burn_subtitles(str(video), str(active_bilingual_srt), str(output_video))

    except KeyboardInterrupt:
        _write_web_progress(
            args.web_progress_file,
            primary_status="failed",
            enhancement_status="pending",
            current_stage="failed",
            primary_error_text="cancelled by user",
        )
        print("\n\033[31m[interrupted]\033[0m cancelled by user")
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        _write_web_progress(
            args.web_progress_file,
            primary_status="failed",
            enhancement_status="pending",
            current_stage="failed",
            primary_error_text=str(exc),
        )
        print("\n\033[31m[error]\033[0m subtitle generation failed")
        print(f"  {exc}")
        sys.exit(1)

    final_artifacts = list(draft_artifacts)
    if args.ai_review != "off" and ai_cn_review_applied:
        final_artifacts.append(_progress_artifact(reviewed_cn_srt, "reviewed_subtitle"))
    if args.ai_review != "off" and ai_bilingual_review_applied:
        final_artifacts.append(_progress_artifact(active_bilingual_srt, "reviewed_bilingual_subtitle"))
    if enhancement_failed:
        _write_web_progress(
            args.web_progress_file,
            primary_status="draft_ready",
            enhancement_status="failed",
            current_stage="draft_ready",
            artifacts=final_artifacts,
            enhancement_error_text=enhancement_error_text,
        )
    else:
        _write_web_progress(
            args.web_progress_file,
            primary_status="completed",
            enhancement_status="succeeded" if args.ai_review != "off" else "skipped",
            current_stage="completed",
            artifacts=final_artifacts,
        )

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
