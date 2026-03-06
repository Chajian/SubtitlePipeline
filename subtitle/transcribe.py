"""Whisper 语音识别与翻译"""

import sys
from faster_whisper import WhisperModel
from config import MODEL_SIZE, DEVICE, COMPUTE_TYPE, SOURCE_LANGUAGE


def _load_model():
    """加载 faster-whisper 模型（首次调用时下载）"""
    print(f"\033[36m[模型]\033[0m 加载 {MODEL_SIZE}（设备={DEVICE}, 精度={COMPUTE_TYPE}）...")
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print(f"\033[32m[模型]\033[0m 加载完成")
    return model


def _run_whisper(video_path, task, language=None):
    """
    调用 faster-whisper 执行识别或翻译。

    Parameters
    ----------
    video_path : str
    task : str   "transcribe" | "translate"
    language : str | None  指定源语言（translate 时也需要指定以提高质量）

    Returns
    -------
    list[tuple[float, float, str]]  [(start, end, text), ...]
    """
    model = _load_model()

    task_label = "识别中文" if task == "transcribe" else "翻译英文"
    print(f"\033[36m[{task_label}]\033[0m 处理中: {video_path}")

    segments_iter, info = model.transcribe(
        video_path,
        task=task,
        language=language,
        beam_size=5,
        vad_filter=True,           # VAD 过滤静音段
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )

    segments = []
    for seg in segments_iter:
        segments.append((seg.start, seg.end, seg.text.strip()))
        # 实时打印进度
        sys.stdout.write(
            f"\r\033[33m[{task_label}]\033[0m "
            f"{seg.end:.1f}s / {info.duration:.1f}s "
            f"({seg.end / info.duration * 100:.0f}%)"
        )
        sys.stdout.flush()

    print()  # 换行
    print(f"\033[32m[{task_label}]\033[0m 完成，共 {len(segments)} 条字幕")
    return segments


def transcribe_chinese(video_path):
    """识别视频中的中文语音 → [(start, end, text), ...]"""
    return _run_whisper(video_path, task="transcribe", language=SOURCE_LANGUAGE)


def translate_to_english(video_path):
    """将视频语音翻译为英文 → [(start, end, text), ...]"""
    return _run_whisper(video_path, task="translate", language=SOURCE_LANGUAGE)
