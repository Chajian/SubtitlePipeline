"""AI helpers for subtitle review and text-based translation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import uuid4

from subtitle.srt import format_time, parse_srt


@dataclass(slots=True)
class SubtitleTextBlock:
    """A single subtitle line with stable timing and index."""

    index: int
    start: str
    end: str
    text: str


@dataclass(slots=True)
class BilingualSubtitleBlock:
    """A single bilingual subtitle block without timestamps changes."""

    index: int
    start: str
    end: str
    primary_text: str
    english_text: str


@dataclass(slots=True)
class AIReviewSettings:
    """Runtime settings for subtitle review providers."""

    mode: str = "auto"
    provider: str = "codex"
    command: str = "codex"
    model: str | None = None
    base_url: str | None = None
    max_blocks_per_chunk: int = 80
    max_chars_per_chunk: int = 12_000
    timeout_seconds: int = 600
    max_attempts: int = 2


def segments_to_text_blocks(segments: list[tuple[float, float, str]]) -> list[SubtitleTextBlock]:
    """Convert timed text segments into stable text blocks."""
    return [
        SubtitleTextBlock(index=i, start=format_time(start), end=format_time(end), text=text)
        for i, (start, end, text) in enumerate(segments, start=1)
    ]


def text_blocks_to_segments(blocks: Iterable[SubtitleTextBlock]) -> list[tuple[float, float, str]]:
    """Convert text blocks back to timed text segments."""
    return [(_parse_time(block.start), _parse_time(block.end), block.text) for block in blocks]


def load_text_srt(path: str | Path) -> list[SubtitleTextBlock]:
    """Load a one-line-per-block SRT as text blocks."""
    blocks: list[SubtitleTextBlock] = []
    for index, start, end, text in parse_srt(path):
        line = " ".join(part.strip() for part in text.splitlines() if part.strip())
        if not line:
            raise ValueError(f"subtitle block {index} is empty")
        blocks.append(SubtitleTextBlock(index=index, start=start, end=end, text=line))
    return blocks


def write_text_srt(blocks: Iterable[SubtitleTextBlock], path: str | Path) -> Path:
    """Write single-line text blocks back to disk."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        for block in blocks:
            handle.write(f"{block.index}\n")
            handle.write(f"{block.start} --> {block.end}\n")
            handle.write(f"{block.text}\n\n")

    return output_path


def load_bilingual_srt(path: str | Path) -> list[BilingualSubtitleBlock]:
    """Load an SRT file and normalize it into bilingual subtitle blocks."""
    blocks: list[BilingualSubtitleBlock] = []
    for index, start, end, text in parse_srt(path):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError(f"subtitle block {index} is empty")
        primary_text = lines[0]
        english_text = " ".join(lines[1:]).strip()
        blocks.append(
            BilingualSubtitleBlock(
                index=index,
                start=start,
                end=end,
                primary_text=primary_text,
                english_text=english_text,
            )
        )
    return blocks


def write_bilingual_srt(blocks: Iterable[BilingualSubtitleBlock], path: str | Path) -> Path:
    """Write bilingual subtitle blocks back to disk."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        for block in blocks:
            handle.write(f"{block.index}\n")
            handle.write(f"{block.start} --> {block.end}\n")
            handle.write(f"{block.primary_text}\n")
            if block.english_text:
                handle.write(f"{block.english_text}\n")
            handle.write("\n")

    return output_path


def maybe_review_text_segments(
    segments: list[tuple[float, float, str]],
    output_path: str | Path,
    settings: AIReviewSettings,
) -> tuple[list[tuple[float, float, str]], bool]:
    """Review monolingual subtitle text while preserving timings."""
    if settings.mode == "off":
        return segments, False

    if settings.provider == "codex" and shutil.which(settings.command) is None:
        if settings.mode == "on":
            raise RuntimeError(f"AI review command not found: {settings.command}")
        print(
            f"\033[33m[AI]\033[0m Skip Chinese subtitle review because "
            f"`{settings.command}` is not available in PATH."
        )
        return segments, False

    try:
        reviewed_blocks = review_text_blocks(segments_to_text_blocks(segments), settings)
    except Exception as exc:  # noqa: BLE001
        if settings.mode == "on":
            raise
        print(f"\033[33m[AI]\033[0m Chinese subtitle review skipped: {exc}")
        return segments, False

    write_text_srt(reviewed_blocks, output_path)
    print(f"\033[32m[AI]\033[0m Reviewed Chinese subtitles written to {output_path}")
    return text_blocks_to_segments(reviewed_blocks), True


def translate_text_segments_to_english(
    segments: list[tuple[float, float, str]],
    settings: AIReviewSettings,
) -> list[tuple[float, float, str]]:
    """Translate reviewed source-language text into English, preserving timings."""
    if settings.provider == "codex" and shutil.which(settings.command) is None:
        raise RuntimeError(f"AI translation command not found: {settings.command}")

    source_blocks = segments_to_text_blocks(segments)
    translated_blocks = translate_text_blocks(source_blocks, settings)
    return text_blocks_to_segments(translated_blocks)


def maybe_review_bilingual_srt(
    input_path: str | Path,
    output_path: str | Path,
    settings: AIReviewSettings,
) -> tuple[Path, bool]:
    """
    Review bilingual subtitles when available.

    Returns the path that should be used downstream and whether review succeeded.
    """
    source_path = Path(input_path)
    target_path = Path(output_path)

    if settings.mode == "off":
        return source_path, False

    if settings.provider == "codex" and shutil.which(settings.command) is None:
        if settings.mode == "on":
            raise RuntimeError(f"AI review command not found: {settings.command}")
        print(
            f"\033[33m[AI]\033[0m Skip subtitle review because "
            f"`{settings.command}` is not available in PATH."
        )
        return source_path, False

    try:
        reviewed_blocks = review_bilingual_srt(source_path, settings)
    except Exception as exc:  # noqa: BLE001
        if settings.mode == "on":
            raise
        print(f"\033[33m[AI]\033[0m Subtitle review skipped: {exc}")
        return source_path, False

    write_bilingual_srt(reviewed_blocks, target_path)
    print(f"\033[32m[AI]\033[0m Reviewed subtitles written to {target_path}")
    return target_path, True


def review_text_blocks(
    original_blocks: list[SubtitleTextBlock],
    settings: AIReviewSettings,
) -> list[SubtitleTextBlock]:
    """Run subtitle-text review over monolingual blocks."""
    if not original_blocks:
        raise RuntimeError("no subtitle blocks found for Chinese review")

    chunks = list(
        _chunk_text_blocks(
            original_blocks,
            max_blocks=settings.max_blocks_per_chunk,
            max_chars=settings.max_chars_per_chunk,
        )
    )
    reviewed_blocks: list[SubtitleTextBlock] = []
    total_chunks = len(chunks)
    for chunk_index, chunk in enumerate(chunks, start=1):
        print(
            f"\033[36m[AI]\033[0m Reviewing Chinese subtitle chunk "
            f"{chunk_index}/{total_chunks} ({len(chunk)} blocks)"
        )
        reviewed_blocks.extend(_review_text_chunk(chunk, settings))

    return reviewed_blocks


def translate_text_blocks(
    source_blocks: list[SubtitleTextBlock],
    settings: AIReviewSettings,
) -> list[SubtitleTextBlock]:
    """Translate text blocks into English while preserving timings."""
    if not source_blocks:
        raise RuntimeError("no subtitle blocks found for English translation")

    chunks = list(
        _chunk_text_blocks(
            source_blocks,
            max_blocks=settings.max_blocks_per_chunk,
            max_chars=settings.max_chars_per_chunk,
        )
    )
    translated_blocks: list[SubtitleTextBlock] = []
    total_chunks = len(chunks)
    for chunk_index, chunk in enumerate(chunks, start=1):
        print(
            f"\033[36m[AI]\033[0m Translating reviewed Chinese chunk "
            f"{chunk_index}/{total_chunks} ({len(chunk)} blocks)"
        )
        translated_blocks.extend(_translate_text_chunk(chunk, settings))

    return translated_blocks


def review_bilingual_srt(path: str | Path, settings: AIReviewSettings) -> list[BilingualSubtitleBlock]:
    """Run AI review over bilingual subtitle blocks and return corrected blocks."""
    original_blocks = load_bilingual_srt(path)
    if not original_blocks:
        raise RuntimeError("no subtitle blocks found for AI review")

    chunks = list(
        _chunk_bilingual_blocks(
            original_blocks,
            max_blocks=settings.max_blocks_per_chunk,
            max_chars=settings.max_chars_per_chunk,
        )
    )
    reviewed_blocks: list[BilingualSubtitleBlock] = []
    total_chunks = len(chunks)
    for chunk_index, chunk in enumerate(chunks, start=1):
        print(
            f"\033[36m[AI]\033[0m Reviewing subtitle chunk "
            f"{chunk_index}/{total_chunks} ({len(chunk)} blocks)"
        )
        reviewed_blocks.extend(_review_bilingual_chunk(chunk, settings))

    return reviewed_blocks


def _chunk_text_blocks(
    blocks: list[SubtitleTextBlock],
    *,
    max_blocks: int,
    max_chars: int,
) -> Iterable[list[SubtitleTextBlock]]:
    current_chunk: list[SubtitleTextBlock] = []
    current_chars = 0
    for block in blocks:
        block_chars = len(block.text) + 16
        hit_block_limit = len(current_chunk) >= max_blocks
        hit_char_limit = current_chunk and current_chars + block_chars > max_chars
        if hit_block_limit or hit_char_limit:
            yield current_chunk
            current_chunk = []
            current_chars = 0

        current_chunk.append(block)
        current_chars += block_chars

    if current_chunk:
        yield current_chunk


def _chunk_bilingual_blocks(
    blocks: list[BilingualSubtitleBlock],
    *,
    max_blocks: int,
    max_chars: int,
) -> Iterable[list[BilingualSubtitleBlock]]:
    current_chunk: list[BilingualSubtitleBlock] = []
    current_chars = 0
    for block in blocks:
        block_chars = len(block.primary_text) + len(block.english_text) + 32
        hit_block_limit = len(current_chunk) >= max_blocks
        hit_char_limit = current_chunk and current_chars + block_chars > max_chars
        if hit_block_limit or hit_char_limit:
            yield current_chunk
            current_chunk = []
            current_chars = 0

        current_chunk.append(block)
        current_chars += block_chars

    if current_chunk:
        yield current_chunk


def _review_text_chunk(
    chunk: list[SubtitleTextBlock],
    settings: AIReviewSettings,
) -> list[SubtitleTextBlock]:
    schema = _text_review_schema()
    prompt = _build_text_review_prompt(chunk)
    response = _run_json_task(prompt, schema, settings, action_label="Chinese subtitle review")
    return _validate_text_review_response(chunk, response)


def _translate_text_chunk(
    chunk: list[SubtitleTextBlock],
    settings: AIReviewSettings,
) -> list[SubtitleTextBlock]:
    schema = _text_translation_schema()
    prompt = _build_text_translation_prompt(chunk)
    response = _run_json_task(
        prompt,
        schema,
        settings,
        action_label="English translation",
        validator=lambda payload: _validate_text_translation_response(chunk, payload),
    )
    return _validate_text_translation_response(chunk, response)


def _review_bilingual_chunk(
    chunk: list[BilingualSubtitleBlock],
    settings: AIReviewSettings,
) -> list[BilingualSubtitleBlock]:
    schema = _bilingual_review_schema()
    prompt = _build_bilingual_review_prompt(chunk)
    response = _run_json_task(prompt, schema, settings, action_label="bilingual subtitle review")
    return _validate_bilingual_review_response(chunk, response)


def _run_json_task(
    prompt: str,
    schema: dict[str, object],
    settings: AIReviewSettings,
    *,
    action_label: str,
    validator: Callable[[dict[str, object]], object] | None = None,
) -> dict[str, object]:
    last_error: Exception | None = None
    active_prompt = prompt
    for attempt in range(1, settings.max_attempts + 1):
        try:
            if settings.provider == "codex":
                response = _run_codex_json_task(active_prompt, schema, settings)
            elif settings.provider in {"openai", "siliconflow"}:
                response = _run_openai_compatible_json_task(active_prompt, settings)
            else:
                raise RuntimeError(f"unsupported AI review provider: {settings.provider}")

            if validator is not None:
                validator(response)
            return response
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(
                f"\033[33m[AI]\033[0m {action_label} attempt "
                f"{attempt}/{settings.max_attempts} failed: {exc}"
            )
            if attempt < settings.max_attempts:
                active_prompt = _append_retry_feedback(prompt, action_label, exc)

    assert last_error is not None
    raise RuntimeError(f"{action_label} failed after retries: {last_error}") from last_error


def _run_codex_json_task(
    prompt: str,
    schema: dict[str, object],
    settings: AIReviewSettings,
) -> dict[str, object]:
    temp_root_base = Path.cwd() / ".tmp" / "subtitle-ai-review"
    temp_root_base.mkdir(parents=True, exist_ok=True)
    temp_root = temp_root_base / f"run-{uuid4().hex}"
    temp_root.mkdir(parents=True, exist_ok=True)
    try:
        schema_path = temp_root / "schema.json"
        output_path = temp_root / "result.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=True), encoding="utf-8")

        command = [
            settings.command,
            "exec",
            "-",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
        ]
        if settings.model:
            command.extend(["--model", settings.model])

        completed = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            details = completed.stderr.strip() or completed.stdout.strip() or "unknown codex error"
            raise RuntimeError(details)
        if not output_path.exists():
            raise RuntimeError("codex task did not produce an output file")

        raw_output = output_path.read_text(encoding="utf-8").strip()
        if not raw_output:
            raise RuntimeError("codex task returned empty output")
        return json.loads(raw_output)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def _run_openai_compatible_json_task(
    prompt: str,
    settings: AIReviewSettings,
) -> dict[str, object]:
    model = settings.model or os.getenv("AI_REVIEW_MODEL")
    if not model:
        raise RuntimeError(
            f"AI review model is required for provider `{settings.provider}`. "
            "Use `--ai-review-model` or set `AI_REVIEW_MODEL`."
        )

    api_key = _resolve_api_key(settings.provider)
    base_url = _resolve_base_url(settings)
    endpoint = base_url.rstrip("/") + "/chat/completions"

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You edit and translate subtitle text. "
                    "Return strict JSON only. Keep the same block count and indices."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "response_format": {"type": "json_object"},
    }

    request = urllib_request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(request, timeout=settings.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{settings.provider} API request failed with HTTP {exc.code}: {details}"
        ) from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"{settings.provider} API request failed: {exc.reason}") from exc

    response_payload = json.loads(raw)
    content = _extract_openai_compatible_content(response_payload)
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{settings.provider} API returned non-JSON content: {content}") from exc


def _resolve_api_key(provider: str) -> str:
    generic_key = os.getenv("AI_REVIEW_API_KEY")
    if generic_key:
        return generic_key

    env_map = {
        "openai": "OPENAI_API_KEY",
        "siliconflow": "SILICONFLOW_API_KEY",
    }
    env_name = env_map.get(provider)
    if not env_name:
        raise RuntimeError(f"unsupported AI review provider: {provider}")

    api_key = os.getenv(env_name)
    if not api_key:
        raise RuntimeError(
            f"{provider} API key not found. Set `{env_name}` or `AI_REVIEW_API_KEY`."
        )
    return api_key


def _resolve_base_url(settings: AIReviewSettings) -> str:
    if settings.base_url:
        return settings.base_url

    env_base = os.getenv("AI_REVIEW_BASE_URL")
    if env_base:
        return env_base

    base_url_map = {
        "openai": "https://api.openai.com/v1",
        "siliconflow": "https://api.siliconflow.cn/v1",
    }
    base_url = base_url_map.get(settings.provider)
    if not base_url:
        raise RuntimeError(f"unsupported AI review provider: {settings.provider}")
    return base_url


def _text_review_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "text": {"type": "string"},
                    },
                    "required": ["index", "text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["blocks"],
        "additionalProperties": False,
    }


def _text_translation_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "english_text": {"type": "string"},
                    },
                    "required": ["index", "english_text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["blocks"],
        "additionalProperties": False,
    }


def _bilingual_review_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "primary_text": {"type": "string"},
                        "english_text": {"type": "string"},
                    },
                    "required": ["index", "primary_text", "english_text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["blocks"],
        "additionalProperties": False,
    }


def _build_text_review_prompt(chunk: list[SubtitleTextBlock]) -> str:
    payload = {"blocks": [{"index": block.index, "text": block.text} for block in chunk]}
    return (
        "Review these source-language subtitle blocks before translation.\n"
        "Rules:\n"
        "1. Keep the same block count and same indices.\n"
        "2. Correct ASR mistakes, punctuation, repeated words, and obvious wording issues.\n"
        "3. Preserve the original meaning. Do not add facts.\n"
        "4. Keep the text in the original source language.\n"
        "5. Keep every subtitle to a single line. No newline characters.\n"
        "6. Prefer natural, concise subtitle phrasing.\n"
        "7. Return JSON only.\n\n"
        f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )


def _build_text_translation_prompt(chunk: list[SubtitleTextBlock]) -> str:
    payload = {"blocks": [{"index": block.index, "text": block.text} for block in chunk]}
    return (
        "Translate these reviewed subtitle blocks into English.\n"
        "Hard requirements:\n"
        "1. Return valid JSON only. No markdown, no explanation, no prose outside JSON.\n"
        "2. Output must contain exactly one item for every input block.\n"
        "3. Keep the same indices and order.\n"
        "4. Every block must include a non-empty `english_text`.\n"
        "5. Do not omit any block.\n"
        "6. Do not use null, empty string, or placeholder text.\n"
        "7. Each `english_text` must be a single subtitle line.\n"
        "8. If a block is short or fragmentary, still produce the best possible English subtitle.\n"
        "9. Preserve meaning, but make the English natural and concise.\n"
        "10. Write like subtitles, not like narration.\n"
        "11. Do not add greetings, transitions, or context that is not present in the source block.\n"
        "12. Prefer short subtitle-style phrasing over full explanatory sentences.\n\n"
        "Correct output example:\n"
        '{\n'
        '  "blocks": [\n'
        '    { "index": 1, "english_text": "Hello, everyone." },\n'
        '    { "index": 2, "english_text": "Today I will show you this project." }\n'
        "  ]\n"
        "}\n\n"
        f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )


def _build_bilingual_review_prompt(chunk: list[BilingualSubtitleBlock]) -> str:
    payload = {
        "blocks": [
            {
                "index": block.index,
                "primary_text": block.primary_text,
                "english_text": block.english_text,
            }
            for block in chunk
        ]
    }
    return (
        "Review these bilingual subtitle blocks and correct wording mistakes.\n"
        "Rules:\n"
        "1. Keep the same block count and same indices.\n"
        "2. Improve punctuation, grammar, terminology, and mistranscriptions.\n"
        "3. Preserve original meaning. Do not add facts.\n"
        "4. `primary_text` must stay in the source language.\n"
        "5. `english_text` must stay in English.\n"
        "6. Keep every field to a single subtitle line. No newline characters.\n"
        "7. Return JSON only.\n\n"
        f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )


def _validate_text_review_response(
    original_chunk: list[SubtitleTextBlock],
    response: dict[str, object],
) -> list[SubtitleTextBlock]:
    raw_blocks = response.get("blocks")
    if not isinstance(raw_blocks, list):
        raise ValueError("AI response is missing `blocks` array")
    if len(raw_blocks) != len(original_chunk):
        raise ValueError(f"expected {len(original_chunk)} reviewed blocks, got {len(raw_blocks)}")

    reviewed: list[SubtitleTextBlock] = []
    for original, candidate in zip(original_chunk, raw_blocks, strict=True):
        if not isinstance(candidate, dict):
            raise ValueError("AI returned a non-object subtitle block")

        reviewed_index = candidate.get("index")
        if reviewed_index != original.index:
            raise ValueError(
                f"subtitle block index mismatch: expected {original.index}, got {reviewed_index}"
            )

        text = _sanitize_subtitle_line(candidate.get("text"))
        if not text:
            raise ValueError(f"subtitle block {original.index} has empty text")

        reviewed.append(
            SubtitleTextBlock(index=original.index, start=original.start, end=original.end, text=text)
        )

    return reviewed


def _validate_text_translation_response(
    original_chunk: list[SubtitleTextBlock],
    response: dict[str, object],
) -> list[SubtitleTextBlock]:
    raw_blocks = response.get("blocks")
    if not isinstance(raw_blocks, list):
        raise ValueError("AI response is missing `blocks` array")
    if len(raw_blocks) != len(original_chunk):
        raise ValueError(f"expected {len(original_chunk)} translated blocks, got {len(raw_blocks)}")

    translated: list[SubtitleTextBlock] = []
    for original, candidate in zip(original_chunk, raw_blocks, strict=True):
        if not isinstance(candidate, dict):
            raise ValueError("AI returned a non-object subtitle block")

        reviewed_index = candidate.get("index")
        if reviewed_index != original.index:
            raise ValueError(
                f"subtitle block index mismatch: expected {original.index}, got {reviewed_index}"
            )

        english_text = _sanitize_subtitle_line(candidate.get("english_text"))
        if not english_text:
            raise ValueError(f"subtitle block {original.index} has empty english_text")

        translated.append(
            SubtitleTextBlock(
                index=original.index,
                start=original.start,
                end=original.end,
                text=english_text,
            )
        )

    return translated


def _validate_bilingual_review_response(
    original_chunk: list[BilingualSubtitleBlock],
    response: dict[str, object],
) -> list[BilingualSubtitleBlock]:
    raw_blocks = response.get("blocks")
    if not isinstance(raw_blocks, list):
        raise ValueError("AI response is missing `blocks` array")
    if len(raw_blocks) != len(original_chunk):
        raise ValueError(f"expected {len(original_chunk)} reviewed blocks, got {len(raw_blocks)}")

    reviewed: list[BilingualSubtitleBlock] = []
    for original, candidate in zip(original_chunk, raw_blocks, strict=True):
        if not isinstance(candidate, dict):
            raise ValueError("AI returned a non-object subtitle block")

        reviewed_index = candidate.get("index")
        if reviewed_index != original.index:
            raise ValueError(
                f"subtitle block index mismatch: expected {original.index}, got {reviewed_index}"
            )

        primary_text = _sanitize_subtitle_line(candidate.get("primary_text"))
        english_text = _sanitize_subtitle_line(candidate.get("english_text"))

        if not primary_text:
            raise ValueError(f"subtitle block {original.index} has empty primary_text")
        if original.english_text and not english_text:
            raise ValueError(f"subtitle block {original.index} has empty english_text")

        reviewed.append(
            BilingualSubtitleBlock(
                index=original.index,
                start=original.start,
                end=original.end,
                primary_text=primary_text,
                english_text=english_text,
            )
        )

    return reviewed


def _extract_openai_compatible_content(response_payload: dict[str, object]) -> str:
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("AI review API response is missing `choices`")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("AI review API returned an invalid choice payload")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("AI review API response is missing `message`")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        combined = "".join(parts).strip()
        if combined:
            return combined

    raise RuntimeError("AI review API response is missing text content")


def _append_retry_feedback(base_prompt: str, action_label: str, error: Exception) -> str:
    return (
        f"{base_prompt}\n"
        "Your previous response was invalid.\n"
        f"Task: {action_label}\n"
        f"Validation error: {error}\n"
        "Return the full JSON again.\n"
        "Do not explain.\n"
        "Do not omit any block.\n"
        "Every required field must be present and non-empty.\n"
    )


def _parse_time(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return (int(hours) * 3600) + (int(minutes) * 60) + int(seconds) + int(millis) / 1000.0


def _sanitize_subtitle_line(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())
