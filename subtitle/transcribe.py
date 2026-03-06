"""Whisper 语音识别与翻译。"""

from __future__ import annotations

import sys

from faster_whisper import WhisperModel

from config import COMPUTE_TYPE, DEVICE, MODEL_SIZE, SOURCE_LANGUAGE


def normalize_source_language(language: str | None) -> str:
    """
    归一化源语言参数。

    支持常见简体中文别名：
    - zh
    - zh-cn
    - zh-hans
    - cn
    - chinese
    """
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


def _load_model() -> WhisperModel:
    """加载 faster-whisper 模型（首次调用时会下载）。"""
    print(
        f"\033[36m[模型]\033[0m 加载 {MODEL_SIZE}（设备={DEVICE}, 精度={COMPUTE_TYPE}）..."
    )
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print("\033[32m[模型]\033[0m 加载完成")
    return model


def _run_whisper(video_path: str, task: str, language: str | None) -> list[tuple[float, float, str]]:
    """
    调用 faster-whisper 执行识别或翻译。

    Returns:
        list[(start, end, text), ...]
    """
    model = _load_model()
    normalized_language = normalize_source_language(language)

    task_label = "识别语音" if task == "transcribe" else "翻译英文"
    print(
        f"\033[36m[{task_label}]\033[0m 处理中: {video_path} (language={normalized_language})"
    )

    segments_iter, info = model.transcribe(
        video_path,
        task=task,
        language=normalized_language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    segments: list[tuple[float, float, str]] = []
    for seg in segments_iter:
        segments.append((seg.start, seg.end, seg.text.strip()))
        sys.stdout.write(
            f"\r\033[33m[{task_label}]\033[0m "
            f"{seg.end:.1f}s / {info.duration:.1f}s "
            f"({seg.end / info.duration * 100:.0f}%)"
        )
        sys.stdout.flush()

    print()
    print(f"\033[32m[{task_label}]\033[0m 完成，共 {len(segments)} 条字幕")
    return segments


def transcribe_speech(video_path: str, source_language: str | None = None) -> list[tuple[float, float, str]]:
    """识别视频语音。"""
    return _run_whisper(video_path, task="transcribe", language=source_language or SOURCE_LANGUAGE)


def translate_to_english(video_path: str, source_language: str | None = None) -> list[tuple[float, float, str]]:
    """将视频语音翻译为英文。"""
    return _run_whisper(video_path, task="translate", language=source_language or SOURCE_LANGUAGE)


def transcribe_chinese(video_path: str) -> list[tuple[float, float, str]]:
    """兼容旧接口：识别中文语音。"""
    return transcribe_speech(video_path, source_language="zh")
