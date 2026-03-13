"""Whisper speech transcription and translation helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from faster_whisper import WhisperModel

from config import (
    COMPUTE_TYPE,
    DEVICE,
    MODEL_DIR,
    MODEL_MIRROR_ENDPOINT,
    MODEL_SIZE,
    MODEL_SOURCE,
    SOURCE_LANGUAGE,
)


def normalize_source_language(language: str | None) -> str:
    """Normalize common aliases for the input speech language."""
    if not language:
        return SOURCE_LANGUAGE

    raw = language.strip().lower().replace("_", "-")
    alias_map = {
        "zh": "zh",
        "zh-cn": "zh",
        "zh-hans": "zh",
        "cn": "zh",
        "chinese": "zh",
    }
    return alias_map.get(raw, raw)


def preflight_model_access() -> None:
    """Validate model-related configuration before loading faster-whisper."""
    if MODEL_SOURCE == "local":
        if not MODEL_DIR:
            raise ValueError("--model-source local requires --model-dir")
        model_root = Path(MODEL_DIR)
        if not model_root.exists():
            raise FileNotFoundError(f"local model dir not found: {model_root}")
        candidate = model_root / MODEL_SIZE
        resolved = candidate if candidate.exists() else model_root
        print(f"\033[36m[model]\033[0m Use local model path: {resolved}")
        return

    if MODEL_SOURCE == "mirror":
        if not MODEL_MIRROR_ENDPOINT:
            raise ValueError("--model-source mirror requires --mirror-endpoint")
        print(f"\033[36m[model]\033[0m Use mirror endpoint: {MODEL_MIRROR_ENDPOINT}")
        return

    if MODEL_SOURCE == "official":
        print("\033[36m[model]\033[0m Use official Hugging Face source")
        return

    if MODEL_MIRROR_ENDPOINT:
        print(
            "\033[36m[model]\033[0m Auto mode with mirror fallback: "
            f"{MODEL_MIRROR_ENDPOINT}"
        )
    else:
        print("\033[36m[model]\033[0m Auto mode with default source")


def _resolve_model_reference() -> tuple[str, dict[str, object]]:
    """Translate model source settings into WhisperModel arguments."""
    kwargs: dict[str, object] = {}

    if MODEL_SOURCE == "local":
        if not MODEL_DIR:
            raise ValueError("--model-source local requires --model-dir")
        model_root = Path(MODEL_DIR)
        candidate = model_root / MODEL_SIZE
        return str(candidate if candidate.exists() else model_root), kwargs

    if MODEL_DIR:
        kwargs["download_root"] = MODEL_DIR

    if MODEL_SOURCE in {"mirror", "auto"} and MODEL_MIRROR_ENDPOINT:
        os.environ["HF_ENDPOINT"] = MODEL_MIRROR_ENDPOINT

    return MODEL_SIZE, kwargs


def _load_model() -> WhisperModel:
    """Load the faster-whisper model."""
    model_ref, extra_kwargs = _resolve_model_reference()
    print(
        f"\033[36m[model]\033[0m Loading {model_ref} "
        f"(device={DEVICE}, compute_type={COMPUTE_TYPE})..."
    )
    model = WhisperModel(model_ref, device=DEVICE, compute_type=COMPUTE_TYPE, **extra_kwargs)
    print("\033[32m[model]\033[0m Model ready")
    return model


def _load_model_cpu_fallback() -> WhisperModel:
    """Load the model with a CPU fallback when CUDA runtime is broken."""
    model_ref, extra_kwargs = _resolve_model_reference()
    print(
        "\033[33m[model]\033[0m CUDA runtime unavailable; "
        "falling back to CPU/int8 for this run."
    )
    model = WhisperModel(model_ref, device="cpu", compute_type="int8", **extra_kwargs)
    print("\033[32m[model]\033[0m Model ready (CPU fallback)")
    return model


def _run_whisper(video_path: str, task: str, language: str | None) -> list[tuple[float, float, str]]:
    """Run faster-whisper for either transcription or translation."""
    normalized_language = normalize_source_language(language)

    task_label = "Transcribe" if task == "transcribe" else "Translate"
    print(
        f"\033[36m[{task_label}]\033[0m Processing {video_path} "
        f"(language={normalized_language})"
    )

    def run_once(model: WhisperModel) -> list[tuple[float, float, str]]:
        segments_iter, info = model.transcribe(
            video_path,
            task=task,
            language=normalized_language,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )

        result: list[tuple[float, float, str]] = []
        for seg in segments_iter:
            result.append((seg.start, seg.end, seg.text.strip()))
            sys.stdout.write(
                f"\r\033[33m[{task_label}]\033[0m "
                f"{seg.end:.1f}s / {info.duration:.1f}s "
                f"({seg.end / info.duration * 100:.0f}%)"
            )
            sys.stdout.flush()
        return result

    model = _load_model()
    try:
        segments = run_once(model)
    except Exception as exc:  # noqa: BLE001
        can_fallback_cpu = DEVICE == "cuda" and "cublas64_12.dll" in str(exc).lower()
        if not can_fallback_cpu:
            raise
        model = _load_model_cpu_fallback()
        segments = run_once(model)

    print()
    print(f"\033[32m[{task_label}]\033[0m Completed with {len(segments)} segments")
    return segments


def transcribe_speech(video_path: str, source_language: str | None = None) -> list[tuple[float, float, str]]:
    """Transcribe source speech into subtitle segments."""
    return _run_whisper(video_path, task="transcribe", language=source_language or SOURCE_LANGUAGE)


def translate_to_english(video_path: str, source_language: str | None = None) -> list[tuple[float, float, str]]:
    """Translate source speech into English subtitle segments."""
    return _run_whisper(video_path, task="translate", language=source_language or SOURCE_LANGUAGE)


def transcribe_chinese(video_path: str) -> list[tuple[float, float, str]]:
    """Backward-compatible helper for Chinese transcription."""
    return transcribe_speech(video_path, source_language="zh")
