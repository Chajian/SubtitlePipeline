from __future__ import annotations

import argparse
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import auto_subtitle
from subtitle.debug_trace import DebugTrace
from webapp.service import WebSettings, build_cli_command


class AutoSubtitleMainTest(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        temp_root = Path.cwd() / ".tmp" / "tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_dir = temp_root / f"run-{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return temp_dir

    def test_debug_trace_writes_manifest_and_timeline_for_web_mode(self) -> None:
        temp_dir = self._make_temp_dir()
        trace = DebugTrace(mode="web", root=temp_dir)

        trace.write_manifest({"job_id": "job-123", "status": "draft_ready"})
        trace.append_timeline({"stage": "reviewing", "status": "started"})

        manifest_path = temp_dir / "manifest.json"
        timeline_path = temp_dir / "timeline.jsonl"

        self.assertTrue(manifest_path.exists())
        self.assertTrue(timeline_path.exists())
        self.assertEqual(
            json.loads(manifest_path.read_text(encoding="utf-8")),
            {"job_id": "job-123", "status": "draft_ready"},
        )
        self.assertEqual(
            [
                json.loads(line)
                for line in timeline_path.read_text(encoding="utf-8").splitlines()
            ],
            [{"stage": "reviewing", "status": "started"}],
        )

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
            text_only=False,
            subtitle_track=None,
            merge_mode=None,
            output_format="both",
            burn_only=None,
            web_progress_file=None,
            retry_enhancement=False,
        )

        cn_segments = [(0.0, 1.0, "原文")]
        whisper_en_segments = [(0.0, 1.0, "Whisper fallback")]

        with (
            patch("auto_subtitle.parse_args", return_value=args),
            patch("subtitle.embed.check_ffmpeg"),
            patch("subtitle.embed.burn_subtitles"),
            patch("subtitle.transcribe.preflight_model_access"),
            patch("subtitle.ai_review.preflight_ai_review_access"),
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

    def test_merge_mode_converts_chinese_script_before_writing_outputs(self) -> None:
        temp_dir = self._make_temp_dir()
        video_path = temp_dir / "input.mp4"
        video_path.write_bytes(b"fake")
        output_dir = temp_dir / "output"

        args = argparse.Namespace(
            video=str(video_path),
            model="medium",
            source_language="zh-CN",
            zh_script="simplified",
            model_source="auto",
            model_dir=None,
            mirror_endpoint=None,
            output=str(output_dir),
            ai_review="off",
            ai_review_provider="codex",
            ai_review_model=None,
            ai_review_base_url=None,
            no_burn=True,
            text_only=False,
            subtitle_track="auto",
            merge_mode="prefer-srt",
            output_format="both",
            burn_only=None,
            web_progress_file=None,
            retry_enhancement=False,
        )

        with (
            patch("auto_subtitle.parse_args", return_value=args),
            patch("subtitle.embed.check_ffmpeg"),
            patch("subtitle.embed.burn_subtitles"),
            patch("subtitle.transcribe.preflight_model_access"),
            patch("subtitle.transcribe.transcribe_speech", return_value=[(0.0, 1.0, "繁體")]),
            patch("subtitle.softsub.extract_softsub_segments", return_value=[(0.0, 1.0, "繁體字幕")]),
            patch("auto_subtitle._convert_zh_segments", return_value=[(0.0, 1.0, "简体字幕")]) as convert_zh,
            patch("subtitle.srt.segments_to_txt"),
            patch("subtitle.srt.segments_to_srt") as write_srt,
        ):
            auto_subtitle.main()

        convert_zh.assert_called_once_with([(0.0, 1.0, "繁體字幕")], "simplified")
        written_segments = write_srt.call_args.args[0]
        self.assertEqual(written_segments, [(0.0, 1.0, "简体字幕")])

    def test_ai_review_mode_skips_downstream_steps_when_transcription_is_empty(self) -> None:
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
            ai_review="on",
            ai_review_provider="siliconflow",
            ai_review_model="Pro/MiniMaxAI/MiniMax-M2.5",
            ai_review_base_url="https://api.siliconflow.cn/v1",
            no_burn=True,
            text_only=False,
            subtitle_track=None,
            merge_mode=None,
            output_format="both",
            burn_only=None,
            web_progress_file=None,
            retry_enhancement=False,
        )

        with (
            patch("auto_subtitle.parse_args", return_value=args),
            patch("subtitle.embed.check_ffmpeg"),
            patch("subtitle.embed.burn_subtitles"),
            patch("subtitle.transcribe.preflight_model_access"),
            patch("subtitle.ai_review.preflight_ai_review_access"),
            patch("subtitle.transcribe.transcribe_speech", return_value=[]),
            patch("subtitle.ai_review.maybe_review_text_segments") as review_cn,
            patch("subtitle.ai_review.translate_text_segments_to_english") as translate_reviewed,
            patch("subtitle.ai_review.maybe_review_bilingual_srt") as review_bilingual,
            patch("subtitle.transcribe.translate_to_english") as translate_audio,
            patch("subtitle.srt.merge_bilingual") as merge_bilingual,
            patch("subtitle.srt.segments_to_srt") as write_srt,
        ):
            auto_subtitle.main()

        review_cn.assert_not_called()
        translate_reviewed.assert_not_called()
        review_bilingual.assert_not_called()
        translate_audio.assert_not_called()
        merge_bilingual.assert_not_called()
        self.assertEqual(write_srt.call_count, 3)
        self.assertEqual(write_srt.call_args_list[0].args[0], [])
        self.assertEqual(write_srt.call_args_list[1].args[0], [])
        self.assertEqual(write_srt.call_args_list[2].args[0], [])

    def test_web_progress_file_marks_draft_ready_before_ai_review(self) -> None:
        temp_dir = self._make_temp_dir()
        video_path = temp_dir / "input.mp4"
        video_path.write_bytes(b"fake")
        output_dir = temp_dir / "output"
        progress_path = temp_dir / "job-state.json"

        args = argparse.Namespace(
            video=str(video_path),
            model="medium",
            source_language="zh",
            zh_script="simplified",
            model_source="auto",
            model_dir=None,
            mirror_endpoint=None,
            output=str(output_dir),
            ai_review="on",
            ai_review_provider="siliconflow",
            ai_review_model="Pro/MiniMaxAI/MiniMax-M2.5",
            ai_review_base_url="https://api.siliconflow.cn/v1",
            no_burn=True,
            text_only=False,
            subtitle_track=None,
            merge_mode=None,
            output_format="both",
            burn_only=None,
            web_progress_file=str(progress_path),
            retry_enhancement=False,
        )

        cn_segments = [(0.0, 1.0, "原文")]
        en_segments = [(0.0, 1.0, "Draft english")]

        def review_text_side_effect(*_args, **_kwargs):
            payload = json.loads(progress_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["primary_status"], "draft_ready")
            self.assertEqual(payload["enhancement_status"], "reviewing")
            self.assertEqual(payload["current_stage"], "reviewing")
            return (cn_segments, False)

        with (
            patch("auto_subtitle.parse_args", return_value=args),
            patch("subtitle.embed.check_ffmpeg"),
            patch("subtitle.embed.burn_subtitles"),
            patch("subtitle.transcribe.preflight_model_access"),
            patch("subtitle.ai_review.preflight_ai_review_access"),
            patch("subtitle.transcribe.transcribe_speech", return_value=cn_segments),
            patch("subtitle.ai_review.maybe_review_text_segments", side_effect=review_text_side_effect),
            patch("subtitle.ai_review.translate_text_segments_to_english", return_value=en_segments),
            patch("subtitle.ai_review.maybe_review_bilingual_srt", side_effect=lambda source, *_a, **_k: (Path(source), False)),
        ):
            auto_subtitle.main()

        final_payload = json.loads(progress_path.read_text(encoding="utf-8"))
        self.assertEqual(final_payload["primary_status"], "completed")
        self.assertEqual(final_payload["enhancement_status"], "succeeded")

    def test_build_cli_command_forces_no_burn_and_progress_file_for_web_jobs(self) -> None:
        temp_dir = self._make_temp_dir()
        settings = WebSettings.from_env(temp_dir)
        upload_path = temp_dir / "input.mp4"
        output_dir = temp_dir / "jobs" / "job-123" / "output"

        command = build_cli_command(
            settings,
            upload_path,
            output_dir,
            {
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": True,
                "ai_review": True,
            },
        )

        self.assertIn("--no-burn", command)
        self.assertIn("--web-progress-file", command)
        progress_index = command.index("--web-progress-file")
        self.assertEqual(command[progress_index + 1], str(output_dir.parent / "job-state.json"))

    def test_build_cli_command_adds_retry_enhancement_flag_for_requeued_jobs(self) -> None:
        temp_dir = self._make_temp_dir()
        settings = WebSettings.from_env(temp_dir)
        upload_path = temp_dir / "input.mp4"
        output_dir = temp_dir / "jobs" / "job-123" / "output"

        command = build_cli_command(
            settings,
            upload_path,
            output_dir,
            {
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": True,
                "ai_review": True,
                "__retry_enhancement": True,
            },
        )

        self.assertIn("--retry-enhancement", command)

    def test_ai_review_failure_keeps_draft_ready_progress_state(self) -> None:
        temp_dir = self._make_temp_dir()
        video_path = temp_dir / "input.mp4"
        video_path.write_bytes(b"fake")
        output_dir = temp_dir / "output"
        progress_path = temp_dir / "job-state.json"

        args = argparse.Namespace(
            video=str(video_path),
            model="medium",
            source_language="zh",
            zh_script="simplified",
            model_source="auto",
            model_dir=None,
            mirror_endpoint=None,
            output=str(output_dir),
            ai_review="on",
            ai_review_provider="siliconflow",
            ai_review_model="Pro/MiniMaxAI/MiniMax-M2.5",
            ai_review_base_url="https://api.siliconflow.cn/v1",
            no_burn=True,
            text_only=False,
            subtitle_track=None,
            merge_mode=None,
            output_format="both",
            burn_only=None,
            web_progress_file=str(progress_path),
            retry_enhancement=False,
        )

        cn_segments = [(0.0, 1.0, "原文")]
        en_segments = [(0.0, 1.0, "Fallback english")]

        with (
            patch("auto_subtitle.parse_args", return_value=args),
            patch("subtitle.embed.check_ffmpeg"),
            patch("subtitle.embed.burn_subtitles") as burn_subtitles,
            patch("subtitle.transcribe.preflight_model_access"),
            patch("subtitle.ai_review.preflight_ai_review_access"),
            patch("subtitle.transcribe.transcribe_speech", return_value=cn_segments),
            patch(
                "subtitle.ai_review.maybe_review_text_segments",
                side_effect=RuntimeError("expected 80 reviewed blocks, got 79"),
            ),
            patch("subtitle.transcribe.translate_to_english", return_value=en_segments),
            patch("subtitle.ai_review.maybe_review_bilingual_srt") as review_bilingual,
        ):
            auto_subtitle.main()

        payload = json.loads(progress_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["primary_status"], "draft_ready")
        self.assertEqual(payload["enhancement_status"], "failed")
        self.assertEqual(payload["current_stage"], "draft_ready")
        self.assertIn("expected 80 reviewed blocks, got 79", payload["enhancement_error_text"])
        self.assertEqual([artifact["kind"] for artifact in payload["artifacts"]], [
            "draft_subtitle",
            "draft_translation",
            "draft_bilingual_subtitle",
        ])
        review_bilingual.assert_not_called()
        burn_subtitles.assert_not_called()

    def test_retry_enhancement_uses_existing_draft_and_completes_without_asr(self) -> None:
        temp_dir = self._make_temp_dir()
        video_path = temp_dir / "job-123.mp4"
        video_path.write_bytes(b"fake")
        output_dir = temp_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        progress_path = temp_dir / "job-state.json"
        (output_dir / "job-123.cn.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n原文\n\n",
            encoding="utf-8",
        )
        (output_dir / "job-123.en.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nDraft english\n\n",
            encoding="utf-8",
        )
        (output_dir / "job-123.bilingual.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n原文\nDraft english\n\n",
            encoding="utf-8",
        )

        args = argparse.Namespace(
            video=str(video_path),
            model="medium",
            source_language="zh",
            zh_script="simplified",
            model_source="auto",
            model_dir=None,
            mirror_endpoint=None,
            output=str(output_dir),
            ai_review="on",
            ai_review_provider="siliconflow",
            ai_review_model="Pro/MiniMaxAI/MiniMax-M2.5",
            ai_review_base_url="https://api.siliconflow.cn/v1",
            no_burn=True,
            text_only=False,
            subtitle_track=None,
            merge_mode=None,
            output_format="both",
            burn_only=None,
            web_progress_file=str(progress_path),
            retry_enhancement=True,
        )

        en_segments = [(0.0, 1.0, "Retried english")]

        with (
            patch("auto_subtitle.parse_args", return_value=args),
            patch("subtitle.embed.check_ffmpeg"),
            patch("subtitle.embed.burn_subtitles") as burn_subtitles,
            patch("subtitle.transcribe.preflight_model_access"),
            patch("subtitle.ai_review.preflight_ai_review_access"),
            patch("subtitle.ai_review.maybe_review_text_segments", side_effect=lambda segments, *_a, **_k: (segments, False)),
            patch("subtitle.ai_review.translate_text_segments_to_english", return_value=en_segments) as translate_reviewed,
            patch("subtitle.ai_review.maybe_review_bilingual_srt", side_effect=lambda source, *_a, **_k: (Path(source), False)),
            patch("subtitle.transcribe.transcribe_speech") as transcribe_speech,
            patch("subtitle.transcribe.translate_to_english") as translate_audio,
        ):
            auto_subtitle.main()

        transcribe_speech.assert_not_called()
        translate_audio.assert_not_called()
        translate_reviewed.assert_called_once()
        burn_subtitles.assert_not_called()
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["primary_status"], "completed")
        self.assertEqual(payload["enhancement_status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
