from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from subtitle.ai_review import (
    AIReviewSettings,
    BilingualSubtitleBlock,
    SubtitleTextBlock,
    _extract_openai_compatible_content,
    _resolve_api_key,
    _resolve_base_url,
    _validate_bilingual_review_response,
    _validate_text_review_response,
    _validate_text_translation_response,
    load_bilingual_srt,
    text_blocks_to_segments,
    segments_to_text_blocks,
    write_bilingual_srt,
)


class AIReviewHelpersTest(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        temp_root = Path.cwd() / ".tmp" / "tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_dir = temp_root / f"run-{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return temp_dir

    def test_load_bilingual_srt_reads_primary_and_english_lines(self) -> None:
        temp_dir = self._make_temp_dir()
        srt_path = temp_dir / "sample.srt"
        srt_path.write_text(
            "1\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "Ni hao, shi jie\n"
            "Hello, world\n\n"
            "2\n"
            "00:00:03,000 --> 00:00:04,000\n"
            "Di er ju\n"
            "Second line\n\n",
            encoding="utf-8",
        )

        blocks = load_bilingual_srt(srt_path)

        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].primary_text, "Ni hao, shi jie")
        self.assertEqual(blocks[0].english_text, "Hello, world")
        self.assertEqual(blocks[1].index, 2)

    def test_validate_bilingual_review_response_rejects_mismatched_block_count(self) -> None:
        original = [
            BilingualSubtitleBlock(
                index=1,
                start="00:00:01,000",
                end="00:00:02,000",
                primary_text="yuan wen",
                english_text="Original",
            )
        ]

        with self.assertRaisesRegex(ValueError, "expected 1 reviewed blocks"):
            _validate_bilingual_review_response(original, {"blocks": []})

    def test_validate_text_review_response_preserves_timestamps(self) -> None:
        original = [
            SubtitleTextBlock(
                index=1,
                start="00:00:01,000",
                end="00:00:02,000",
                text="yuan wen",
            )
        ]

        reviewed = _validate_text_review_response(
            original,
            {"blocks": [{"index": 1, "text": "xiu zheng hou"}]},
        )

        self.assertEqual(reviewed[0].start, "00:00:01,000")
        self.assertEqual(reviewed[0].end, "00:00:02,000")
        self.assertEqual(reviewed[0].text, "xiu zheng hou")

    def test_validate_text_translation_response_preserves_timestamps(self) -> None:
        original = [
            SubtitleTextBlock(
                index=1,
                start="00:00:01,000",
                end="00:00:02,000",
                text="yuan wen",
            )
        ]

        translated = _validate_text_translation_response(
            original,
            {"blocks": [{"index": 1, "english_text": "corrected text"}]},
        )

        self.assertEqual(translated[0].start, "00:00:01,000")
        self.assertEqual(translated[0].end, "00:00:02,000")
        self.assertEqual(translated[0].text, "corrected text")

    def test_write_bilingual_srt_preserves_timestamps(self) -> None:
        blocks = [
            BilingualSubtitleBlock(
                index=1,
                start="00:00:01,000",
                end="00:00:02,000",
                primary_text="xiu zheng hou de yuan wen",
                english_text="Corrected text",
            )
        ]

        temp_dir = self._make_temp_dir()
        output_path = temp_dir / "reviewed.srt"
        write_bilingual_srt(blocks, output_path)
        written = output_path.read_text(encoding="utf-8")

        self.assertIn("00:00:01,000 --> 00:00:02,000", written)
        self.assertIn("xiu zheng hou de yuan wen", written)
        self.assertIn("Corrected text", written)

    def test_extract_openai_compatible_content_reads_string_content(self) -> None:
        content = _extract_openai_compatible_content(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"blocks":[{"index":1,"primary_text":"a","english_text":"b"}]}'
                        }
                    }
                ]
            }
        )

        self.assertEqual(
            content,
            '{"blocks":[{"index":1,"primary_text":"a","english_text":"b"}]}',
        )

    def test_extract_openai_compatible_content_reads_list_content(self) -> None:
        content = _extract_openai_compatible_content(
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "output_text", "text": '{"blocks":['},
                                {"type": "output_text", "text": '{"index":1,"primary_text":"a","english_text":"b"}'},
                                {"type": "output_text", "text": "]}"},
                            ]
                        }
                    }
                ]
            }
        )

        self.assertEqual(
            content,
            '{"blocks":[{"index":1,"primary_text":"a","english_text":"b"}]}',
        )

    def test_resolve_api_key_prefers_generic_override(self) -> None:
        with patch.dict(os.environ, {"AI_REVIEW_API_KEY": "generic-key"}, clear=False):
            self.assertEqual(_resolve_api_key("openai"), "generic-key")
            self.assertEqual(_resolve_api_key("siliconflow"), "generic-key")

    def test_resolve_api_key_reads_provider_specific_env(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-key"}, clear=True):
            self.assertEqual(_resolve_api_key("openai"), "openai-key")

        with patch.dict(os.environ, {"SILICONFLOW_API_KEY": "silicon-key"}, clear=True):
            self.assertEqual(_resolve_api_key("siliconflow"), "silicon-key")

    def test_resolve_base_url_uses_provider_default(self) -> None:
        openai_settings = AIReviewSettings(provider="openai")
        siliconflow_settings = AIReviewSettings(provider="siliconflow")

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_resolve_base_url(openai_settings), "https://api.openai.com/v1")
            self.assertEqual(_resolve_base_url(siliconflow_settings), "https://api.siliconflow.cn/v1")

    def test_resolve_base_url_prefers_explicit_override(self) -> None:
        settings = AIReviewSettings(provider="openai", base_url="https://example.com/v1")
        self.assertEqual(_resolve_base_url(settings), "https://example.com/v1")

    def test_segments_to_text_blocks_round_trip(self) -> None:
        segments = [(1.0, 2.5, "ni hao"), (3.0, 4.0, "shi jie")]

        blocks = segments_to_text_blocks(segments)
        restored = text_blocks_to_segments(blocks)

        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].index, 1)
        self.assertEqual(blocks[0].text, "ni hao")
        self.assertEqual(restored, segments)


if __name__ == "__main__":
    unittest.main()
