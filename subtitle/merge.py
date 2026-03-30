"""Align and merge subtitle segments from different sources."""

from __future__ import annotations

from dataclasses import dataclass

Segment = tuple[float, float, str]


@dataclass(slots=True)
class AlignedBlock:
    """Aligned ASR/SRT block with shared time range."""

    index: int
    start: float
    end: float
    asr_text: str
    srt_text: str


def _overlap_score(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    overlap = min(a_end, b_end) - max(a_start, b_start)
    if overlap >= 0:
        return overlap + 10.0
    gap = min(abs(a_start - b_end), abs(b_start - a_end))
    return -gap


def align_segments(
    asr_segments: list[Segment],
    srt_segments: list[Segment],
    *,
    max_gap: float = 1.5,
) -> list[AlignedBlock]:
    """Align ASR and SRT segments by time proximity."""
    asr_sorted = sorted(asr_segments, key=lambda item: item[0])
    srt_sorted = sorted(srt_segments, key=lambda item: item[0])
    used_srt_indices: set[int] = set()
    aligned: list[AlignedBlock] = []

    for asr_start, asr_end, asr_text in asr_sorted:
        best_index = None
        best_score = float("-inf")
        for idx, (srt_start, srt_end, _srt_text) in enumerate(srt_sorted):
            if idx in used_srt_indices:
                continue
            if srt_start > asr_end + max_gap:
                break
            if srt_end < asr_start - max_gap:
                continue
            score = _overlap_score(asr_start, asr_end, srt_start, srt_end)
            if score > best_score:
                best_score = score
                best_index = idx

        srt_text = ""
        if best_index is not None:
            used_srt_indices.add(best_index)
            srt_text = srt_sorted[best_index][2]

        aligned.append(
            AlignedBlock(
                index=0,
                start=asr_start,
                end=asr_end,
                asr_text=asr_text,
                srt_text=srt_text,
            )
        )

    for idx, (srt_start, srt_end, srt_text) in enumerate(srt_sorted):
        if idx in used_srt_indices:
            continue
        aligned.append(
            AlignedBlock(
                index=0,
                start=srt_start,
                end=srt_end,
                asr_text="",
                srt_text=srt_text,
            )
        )

    aligned.sort(key=lambda item: item.start)
    for index, block in enumerate(aligned, start=1):
        block.index = index
    return aligned


def merge_blocks_prefer_srt(blocks: list[AlignedBlock]) -> list[Segment]:
    """Merge aligned blocks by preferring soft subtitle text."""
    merged: list[Segment] = []
    for block in blocks:
        text = block.srt_text or block.asr_text
        if not text:
            continue
        merged.append((block.start, block.end, text))
    return merged


def merge_blocks_prefer_asr(blocks: list[AlignedBlock]) -> list[Segment]:
    """Merge aligned blocks by preferring ASR text."""
    merged: list[Segment] = []
    for block in blocks:
        text = block.asr_text or block.srt_text
        if not text:
            continue
        merged.append((block.start, block.end, text))
    return merged
