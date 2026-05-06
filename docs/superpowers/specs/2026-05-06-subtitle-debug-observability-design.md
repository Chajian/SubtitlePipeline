# Subtitle Debug Observability Design

Date: 2026-05-06

## Goal

Add a practical debug and observability system for the subtitle pipeline so failures can be diagnosed from retained evidence instead of inferred only from terminal errors and coarse logs.

The system should:

- Preserve enough evidence to explain why a pipeline stage failed.
- Cover the full subtitle workflow, not only AI review.
- Default to lightweight diagnostics for web jobs.
- Keep full debug capture as an explicit CLI opt-in.
- Retain failed-task evidence longer than successful-task evidence.

## Scope

In scope:

- Stage-level structured diagnostics for:
  - transcription
  - Chinese subtitle review
  - reviewed-text English translation
  - bilingual subtitle review
  - burn-in
- Per-job debug manifests and timeline events.
- Failure artifact capture for AI chunk processing.
- Machine-readable error codes.
- Retention policy for web diagnostics.
- CLI `--debug` support for full diagnostic capture.

Out of scope:

- Changing the subtitle algorithm itself.
- Chunk-size tuning as the primary fix.
- Centralized log aggregation.
- External observability backends.
- Full tracing infrastructure.
- Replacing human-readable job logs.

## Existing Problems

The current system logs enough to show that a stage failed, but not enough to explain why.

Example symptom already observed in production-like testing:

- `expected 80 reviewed blocks, got 79`

From the current logs we can infer:

- The failure happened during Chinese subtitle review.
- It occurred on chunk `3/4`.
- The chunk contained `80` input blocks.

But we cannot directly answer:

- What exact input blocks were sent to the AI provider?
- What exact provider response came back?
- Whether the model omitted a block, merged blocks, produced malformed JSON, or returned an unexpected schema.
- Whether parsing lost a block before validation.

This leaves the system in a state where parameter guesses are easier than root-cause diagnosis.

## Recommended Approach

Add a two-tier debug system:

1. Web jobs always write lightweight structured diagnostics.
2. CLI runs write full diagnostics only when `--debug` is enabled.

This preserves operational evidence for remote jobs without making every local run noisy or expensive.

## Operating Modes

### Web Default Mode

Web jobs should always write compact diagnostics automatically.

Included by default:

- job-level manifest
- stage timeline
- stage summaries
- failure summaries
- failed AI chunk input/output evidence

Not included by default:

- full successful chunk payload archives for every stage
- all successful provider raw responses

### CLI Default Mode

CLI runs should keep their current lightweight console/log behavior unless the user explicitly opts in.

Default CLI behavior:

- no full diagnostic directory
- no request/response archival

### CLI Debug Mode

When the user passes `--debug`, the pipeline should write complete diagnostic artifacts.

Included:

- all stage summaries
- all stage timing
- all AI chunk requests and responses
- parsed chunk data
- validation failures
- fallback decisions

## Diagnostic Outputs

Each run should have a diagnostic root under the job output directory or a stable sibling path.

Recommended layout:

```text
output/
  debug/
    manifest.json
    timeline.jsonl
    stages/
      transcribe.json
      review-cn.json
      translate-reviewed.json
      review-bilingual.json
      burn.json
    ai-review/
      chunk-01.request.json
      chunk-01.response.txt
      chunk-01.parsed.json
      chunk-01.error.json
```

For web jobs, only the files required by the compact policy need to exist.

## Job-Level Manifest

Each run should emit one machine-readable manifest.

Suggested fields:

- `job_id`
- `source_path`
- `source_filename`
- `source_size_bytes`
- `mode`
  - `web_compact`
  - `cli_default`
  - `cli_debug`
- `provider`
- `model`
- `pipeline_version`
- `started_at`
- `completed_at`
- `result`
  - `completed`
  - `partial_success`
  - `failed`
- `primary_status`
- `enhancement_status`

Purpose:

- Give one stable entrypoint for all diagnostic consumers.

## Timeline Events

Write append-only timeline records to `timeline.jsonl`.

Each record should include:

- `timestamp`
- `stage`
- `event`
- `status`
- `job_id`
- optional `chunk_index`
- optional `message`

Example events:

- `transcribe.started`
- `transcribe.completed`
- `review_cn.chunk_started`
- `review_cn.chunk_failed`
- `translate_reviewed.fallback_triggered`
- `burn.skipped`
- `burn.completed`

Purpose:

- Reconstruct what happened without scraping human log lines.

## Stage Summaries

Each stage should emit one summary JSON file when it completes or fails.

Suggested fields:

- `stage`
- `started_at`
- `completed_at`
- `duration_ms`
- `status`
- `error_code`
- `error_message`
- `input_count`
- `output_count`
- `input_chars`
- `output_chars`
- `provider`
- `model`

Purpose:

- Let developers answer “what failed, how far did it get, and what changed?” quickly.

## AI Chunk Evidence

This is the most important new evidence path because current failures are least diagnosable there.

For failed AI chunks, retain:

- `chunk-XX.request.json`
  - exact chunk metadata and prompt payload
- `chunk-XX.response.txt`
  - raw provider output before parsing
- `chunk-XX.parsed.json`
  - parsed structured response if parsing succeeded partially
- `chunk-XX.error.json`
  - machine-readable validation or parsing failure

For web compact mode:

- retain only failed chunk artifacts

For CLI debug mode:

- retain all chunk artifacts, including successful chunks

## Error Taxonomy

Add explicit machine-readable error codes instead of relying only on human exception strings.

Initial recommended set:

- `transcribe_failed`
- `translation_fallback_triggered`
- `translation_failed`
- `ai_review_json_parse_error`
- `ai_review_block_count_mismatch`
- `ai_review_missing_block`
- `ai_review_duplicate_block`
- `ai_review_schema_error`
- `ai_review_provider_error`
- `burn_failed`

Important rule:

- Human-readable messages remain useful, but every retained diagnostic failure should also have a stable `error_code`.

## Retention Policy

### Web Successful Jobs

Retain compact diagnostics for the same duration as successful job outputs.

Recommended retention:

- `24h`

### Web Failed or Partial-Success Jobs

Retain compact diagnostics longer because these runs are more likely to require investigation.

Recommended retention:

- `72h`

### CLI Debug Runs

Do not auto-delete full diagnostics.

Rationale:

- A user who explicitly enabled debug mode is doing local investigation and should control cleanup manually.

## Web Behavior

Web jobs should expose diagnostic state indirectly through job status and optionally through a future diagnostic download route.

For phase one of this observability work:

- no new public UI is required
- the diagnostics only need to exist on disk
- job detail may later expose a simple `debug_available` flag if useful

This keeps the first observability release operationally valuable without adding unnecessary frontend scope.

## CLI Behavior

Add `--debug` to the CLI.

Behavior:

- when omitted, keep current behavior
- when present, write full diagnostic artifacts

This flag should apply regardless of whether the pipeline succeeds or fails.

## Privacy and Storage Constraints

Because web jobs may contain user media-derived text, compact mode should avoid retaining unnecessary successful raw payloads.

Guidelines:

- keep only what is needed to debug failures by default
- do not archive all successful provider responses in web mode
- prefer stage summaries and failed chunk evidence over blanket raw dumps

## Definition of Done

This observability change is complete when:

- Every major pipeline stage writes structured stage summaries.
- Web jobs always write compact diagnostics.
- CLI `--debug` writes full diagnostics.
- AI chunk failures retain enough request/response evidence to explain block-count mismatches.
- Error conditions use machine-readable error codes.
- Retention behavior differs between successful web jobs and failed or partial-success web jobs.
- Developers can diagnose a failure like `expected 80 reviewed blocks, got 79` from retained artifacts instead of guessing from terminal logs alone.
