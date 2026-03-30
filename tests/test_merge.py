from __future__ import annotations

import unittest

from subtitle.merge import align_segments, merge_blocks_prefer_asr, merge_blocks_prefer_srt


class MergeHelpersTest(unittest.TestCase):
    def test_align_segments_includes_unmatched_blocks(self) -> None:
        asr_segments = [(0.0, 1.0, "asr one"), (2.0, 3.0, "asr two")]
        srt_segments = [(0.0, 1.0, "srt one"), (4.0, 5.0, "srt three")]

        aligned = align_segments(asr_segments, srt_segments)

        self.assertEqual(len(aligned), 3)
        self.assertEqual(aligned[0].srt_text, "srt one")
        self.assertEqual(aligned[1].asr_text, "asr two")
        self.assertEqual(aligned[2].srt_text, "srt three")

    def test_merge_blocks_prefer_srt(self) -> None:
        asr_segments = [(0.0, 1.0, "asr one")]
        srt_segments = [(0.0, 1.0, "srt one")]

        aligned = align_segments(asr_segments, srt_segments)
        merged = merge_blocks_prefer_srt(aligned)

        self.assertEqual(merged, [(0.0, 1.0, "srt one")])

    def test_merge_blocks_prefer_asr(self) -> None:
        asr_segments = [(0.0, 1.0, "asr one")]
        srt_segments = [(0.0, 1.0, "srt one")]

        aligned = align_segments(asr_segments, srt_segments)
        merged = merge_blocks_prefer_asr(aligned)

        self.assertEqual(merged, [(0.0, 1.0, "asr one")])


if __name__ == "__main__":
    unittest.main()
