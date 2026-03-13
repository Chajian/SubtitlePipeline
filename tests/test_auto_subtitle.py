from __future__ import annotations

import argparse
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import auto_subtitle


class AutoSubtitleMainTest(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        temp_root = Path.cwd() / ".tmp" / "tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_dir = temp_root / f"run-{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return temp_dir

    def test_auto_mode_falls_back_to_whisper_translation_when_ai_text_translate_fails(self) -> None:
        temp_dir = self._make_temp_dir()
        video_path = temp_dir / "input.mp4"
        video_path.write_bytes(b"fake")
        output_dir = temp_dir / "output"

        args = argparse.Namespace(
            video=str(video_path),
            model="medium",
            source_language="zh",
            zh_script="simplified",
            model_source="auto",
            model_dir=None,
            mirror_endpoint=None,
            output=str(output_dir),
            ai_review="auto",
            ai_review_provider="siliconflow",
            ai_review_model="Pro/MiniMaxAI/MiniMax-M2.5",
            ai_review_base_url="https://api.siliconflow.cn/v1",
            no_burn=True,
            burn_only=None,
        )

        cn_segments = [(0.0, 1.0, "原文")]
        whisper_en_segments = [(0.0, 1.0, "Whisper fallback")]

        with (
            patch("auto_subtitle.parse_args", return_value=args),
            patch("subtitle.embed.check_ffmpeg"),
            patch("subtitle.embed.burn_subtitles"),
            patch("subtitle.transcribe.preflight_model_access"),
            patch("subtitle.transcribe.transcribe_speech", return_value=cn_segments),
            patch(
                "subtitle.transcribe.translate_to_english",
                return_value=whisper_en_segments,
            ) as whisper_translate,
            patch(
                "subtitle.ai_review.maybe_review_text_segments",
                return_value=(cn_segments, False),
            ),
            patch(
                "subtitle.ai_review.translate_text_segments_to_english",
                side_effect=RuntimeError("translation schema mismatch"),
            ),
            patch(
                "subtitle.ai_review.maybe_review_bilingual_srt",
                side_effect=lambda source, *_args, **_kwargs: (Path(source), False),
            ),
            patch("subtitle.srt.segments_to_srt"),
            patch("subtitle.srt.merge_bilingual"),
        ):
            auto_subtitle.main()

        whisper_translate.assert_called_once_with(str(video_path), source_language="zh")


if __name__ == "__main__":
    unittest.main()
