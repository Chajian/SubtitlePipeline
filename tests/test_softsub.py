from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from subtitle.softsub import SubtitleStream, _select_stream, extract_softsub_segments


class SoftSubExtractTest(unittest.TestCase):
    def test_extract_softsub_segments_auto_selects_language(self) -> None:
        probe_payload = {
            "streams": [
                {"index": 2, "tags": {"language": "eng"}},
                {"index": 3, "tags": {"language": "zho"}},
            ]
        }
        srt_text = (
            "1\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "Ni hao\n"
            "Shi jie\n\n"
        )
        commands: list[list[str]] = []

        def fake_run(command, **_kwargs):
            commands.append(command)
            if command[0] == "ffprobe":
                return _make_completed(stdout=json.dumps(probe_payload), returncode=0)
            if command[0] == "ffmpeg":
                return _make_completed(stdout=srt_text, returncode=0)
            raise AssertionError("unexpected command")

        with patch("subtitle.softsub.subprocess.run", side_effect=fake_run):
            segments = extract_softsub_segments("input.mp4", "auto")

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][2], "Ni hao Shi jie")
        self.assertIn("-map", commands[1])
        self.assertIn("0:s:1", commands[1])

    def test_select_stream_auto_prefers_source_language(self) -> None:
        streams = [
            SubtitleStream(stream_index=2, subtitle_index=0, language="zho"),
            SubtitleStream(stream_index=3, subtitle_index=1, language="jpn"),
            SubtitleStream(stream_index=4, subtitle_index=2, language="eng"),
        ]

        selected = _select_stream(streams, "auto", source_language="ja")

        self.assertEqual(selected.stream_index, 3)


def _make_completed(stdout: str, returncode: int = 0):
    class Result:
        def __init__(self):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    return Result()


if __name__ == "__main__":
    unittest.main()
