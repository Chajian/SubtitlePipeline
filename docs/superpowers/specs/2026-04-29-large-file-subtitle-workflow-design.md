# Large File Subtitle Workflow Design

Date: 2026-04-29

## Goal

Redesign the web subtitle workflow so remote users can submit large media files without coupling upload, media preparation, subtitle generation, and AI enhancement into one brittle path.

The system should:

- Continue supporting remote browser uploads as the primary input path.
- Treat subtitle draft generation as the primary success path.
- Isolate AI review and other enhancement steps so they cannot invalidate an already usable draft.
- Improve status reporting for large jobs with explicit stage transitions.
- Prepare the architecture for later chunked upload and resumable transfer work without requiring that in phase one.

## Scope

In scope:

- Keep whole-file upload for phase one.
- Split the workflow conceptually into ingest, preprocessing, primary subtitle generation, and enhancement stages.
- Add explicit primary and enhancement status modeling.
- Return draft artifacts as soon as they are ready.
- Allow enhancement retry without rerunning upload and ASR.
- Update API and UI semantics around partial success.

Out of scope:

- Chunked upload.
- Resumable upload.
- Object storage migration.
- Real-time streaming transcription while upload is in progress.
- Full multi-tenant authorization design.
- Subtitle burn-in as part of the primary web workflow.

## Existing Constraints

- The current web flow uploads the full file to local disk before creating the job.
- The current worker path is oriented around the CLI pipeline in `auto_subtitle.py`.
- The current web backend stores job state in SQLite under `web_data/app.db`.
- The current web UI is a static `index.html` served by FastAPI.
- The current AI review path can fail hard on malformed or incomplete reviewed block counts, for example: `expected 80 reviewed blocks, got 79`.
- Remote users must remain supported, so local-path submission cannot be the primary product path.

## Problem Summary

The current design treats one large uploaded video as one monolithic pipeline:

1. Upload file.
2. Persist file.
3. Run the full subtitle pipeline.
4. Fail the whole task if later enhancement steps fail.

This creates the wrong failure and product boundaries for large files:

- Upload cost is high, so users need clearer intermediate states.
- The product goal is “get subtitles,” but the system currently behaves like “complete the entire enhancement pipeline or fail.”
- AI enhancement errors are currently able to poison an otherwise successful transcription run.
- Later large-file improvements such as chunked upload would be forced into a workflow whose task boundaries are already wrong.

## Recommended Approach

Use a staged job architecture while keeping phase-one transport simple:

1. Keep whole-file upload in `POST /api/jobs`.
2. After upload completes, hand off to an asynchronous staged workflow.
3. Separate the primary subtitle path from optional enhancement steps.
4. Surface partial success explicitly in the API and UI.
5. Defer chunked and resumable upload until the new task model is stable.

This is the smallest architecture correction that supports remote users now and creates the correct seam for large-file improvements later.

## Architecture

### Web Ingest Layer

Responsibilities:

- Accept the uploaded file.
- Validate basic file type and upload limits.
- Persist the original media file.
- Create the job record.
- Return the job identifier and initial staged status.

Non-responsibilities:

- No subtitle logic.
- No AI review logic.
- No output artifact decisions beyond basic metadata.

### Media Preprocessing Layer

Responsibilities:

- Inspect the uploaded media.
- Determine whether the source is audio or video.
- Extract or normalize audio into a standard worker input.
- Record normalized media metadata such as size and duration when available.

Output:

- A normalized audio input path for downstream subtitle work.

### Primary Subtitle Layer

Responsibilities:

- Consume normalized audio.
- Run ASR and translation steps required for the initial deliverable.
- Produce the first usable draft subtitle artifacts.

Primary success condition:

- Draft Chinese subtitles are generated and downloadable.

This layer must be considered complete even if later AI enhancement does not succeed.

### Enhancement Layer

Responsibilities:

- Run AI subtitle review and refinement.
- Produce reviewed or bilingual artifacts when enabled.
- Record enhancement-specific failures without invalidating existing draft outputs.

This layer is optional from the perspective of primary job success.

### Orchestration Layer

Responsibilities:

- Advance the staged workflow.
- Persist status transitions.
- Distinguish primary failures from enhancement failures.
- Support targeted retries, especially enhancement-only retries.

### Artifact Layer

Responsibilities:

- Track draft and enhanced outputs with explicit kinds and readiness state.
- Expose only available artifacts to the UI.

Representative artifact kinds:

- `draft_subtitle`
- `draft_text`
- `reviewed_subtitle`
- `bilingual_subtitle`
- `log`

## Status Model

The external status model should no longer be a single overloaded field.

### Primary Status

Add `primary_status` with these values:

- `uploading`
- `uploaded`
- `preprocessing`
- `transcribing`
- `draft_ready`
- `completed`
- `failed`

Semantics:

- `draft_ready` means the primary deliverable is available.
- `completed` means the primary path is complete and no more primary work remains.
- `failed` means the main subtitle path failed before a usable draft was produced.

### Enhancement Status

Add `enhancement_status` with these values:

- `pending`
- `reviewing`
- `succeeded`
- `failed`
- `skipped`

Semantics:

- `failed` here does not imply total job failure.
- `skipped` is used when AI enhancement is disabled or intentionally bypassed.

### Current Stage

Add `current_stage` as a UI-facing progress field. Example values:

- `uploaded`
- `extracting_audio`
- `transcribing`
- `writing_draft`
- `reviewing`
- `finalizing`

This field is descriptive and not a replacement for status fields.

### Partial Success

The key supported partial-success state is:

- `primary_status = draft_ready`
- `enhancement_status = failed`

This must be treated as a usable, successful subtitle outcome with degraded enhancement.

## API Design

### `POST /api/jobs`

Keep the current upload endpoint, but change the response semantics to staged job creation.

Response example:

```json
{
  "job_id": "abc123",
  "primary_status": "uploaded",
  "enhancement_status": "pending",
  "filename": "video.mts",
  "size_bytes": 2124644352
}
```

### `GET /api/jobs`

Return recent jobs with staged status fields.

List item fields:

- `job_id`
- `original_filename`
- `primary_status`
- `enhancement_status`
- `current_stage`
- `created_at`
- `updated_at`
- `draft_ready_at`
- `completed_at`

### `GET /api/jobs/{job_id}`

Return full staged detail for one job.

Fields:

- Primary and enhancement status fields
- Stage message or current stage
- Primary and enhancement error text
- Output artifacts
- Existing timestamps and option metadata

Example partial-success response:

```json
{
  "job_id": "abc123",
  "primary_status": "draft_ready",
  "enhancement_status": "failed",
  "current_stage": "review_failed",
  "stage_message": "AI review failed; draft subtitles remain available",
  "primary_error_text": null,
  "enhancement_error_text": "expected 80 reviewed blocks, got 79",
  "files": [
    {"name": "video.cn.srt", "kind": "draft_subtitle"},
    {"name": "video.cn.txt", "kind": "draft_text"}
  ]
}
```

### `POST /api/jobs/{job_id}/retry-enhancement`

Add a targeted retry route for rerunning only the enhancement stage after a draft already exists.

Behavior:

- Valid only when a draft artifact exists.
- Must not rerun upload, preprocessing, or transcription.
- Resets `enhancement_status` to `pending` and requeues enhancement work.

### Optional Later Route

`POST /api/jobs/{job_id}/retry-primary` may be added later for primary-path failures, but it is not required in phase one.

## Data Model

Phase one should prefer extending the current `jobs` table rather than introducing a full relational job graph immediately.

Add fields to the existing job record model:

- `primary_status`
- `enhancement_status`
- `current_stage`
- `media_kind`
- `ingest_size_bytes`
- `normalized_audio_path`
- `draft_ready_at`
- `completed_at`
- `primary_error_text`
- `enhancement_error_text`
- `artifacts_json`

### Artifact Metadata

Use `artifacts_json` in phase one instead of a separate artifact table.

Example:

```json
[
  {"name": "video.cn.srt", "kind": "draft_subtitle", "status": "ready"},
  {"name": "video.cn.txt", "kind": "draft_text", "status": "ready"},
  {"name": "video.bilingual.srt", "kind": "reviewed_subtitle", "status": "failed"}
]
```

This keeps the migration surface small while still giving the UI enough fidelity.

## Workflow Behavior

### Normal Success Path

1. Upload completes.
2. Job enters `uploaded`.
3. Preprocessing extracts or normalizes audio.
4. Job enters `transcribing`.
5. Draft subtitle artifacts are written.
6. Job enters `draft_ready`.
7. If enhancement is disabled, mark `enhancement_status = skipped` and transition primary to `completed`.
8. If enhancement is enabled, keep draft artifacts available while enhancement proceeds.
9. When enhancement succeeds, mark `enhancement_status = succeeded` and finalize `completed`.

### Partial Success Path

1. Draft is produced successfully.
2. Enhancement begins.
3. Enhancement fails.
4. Preserve draft artifacts.
5. Set `enhancement_status = failed`.
6. Keep the job user-visible as usable, not fully failed.

### Primary Failure Path

1. Upload succeeds.
2. Preprocessing or transcription fails before a draft exists.
3. Set `primary_status = failed`.
4. Record `primary_error_text`.
5. Do not present the task as partially successful.

## Frontend Behavior

The web page should shift from a binary “running or done” view to a staged task view.

### Job List

Each job row should show:

- Filename
- Primary status
- Enhancement status when relevant
- Short stage text such as `extracting audio`, `transcribing`, `draft ready`, or `review failed`

### Detail View

The selected job detail should clearly communicate:

- Whether draft subtitles are already available
- Whether enhancement is still running, succeeded, failed, or skipped
- Which files are currently downloadable

### Messaging

Recommended user-facing messages:

- `上传完成，正在提取音频`
- `正在转写字幕`
- `初稿已生成，可下载`
- `AI 校对进行中`
- `AI 校对失败，初稿仍可下载`

## Error Handling

Primary-path failures:

- Must set `primary_status = failed`
- Must record `primary_error_text`
- Must not masquerade as enhancement-only failures

Enhancement failures:

- Must not delete draft outputs
- Must set `enhancement_status = failed`
- Must record `enhancement_error_text`
- Must keep retry available when appropriate

Upload failures:

- Continue returning normal HTTP upload errors
- Remain outside the asynchronous processing lifecycle

## Migration Strategy

### Phase One

- Keep whole-file upload.
- Introduce staged statuses.
- Split primary and enhancement semantics.
- Produce draft-first outputs.
- Convert AI review to an enhancement step that cannot invalidate the draft.

### Phase Two

- Add chunked upload.
- Add resumable upload.
- Consider object storage or external media staging.
- Introduce richer retry and retention policies.

The important rule is: phase one fixes task boundaries first, not upload protocol first.

## Testing

Add regression coverage for:

- New staged status transitions.
- Draft artifacts becoming available before enhancement completes.
- Enhancement failure preserving draft artifacts.
- `retry-enhancement` rerunning only enhancement work.
- List and detail endpoints returning the new status fields.
- Frontend rendering of partial success.

Specific failure coverage should include the current AI review mismatch class where reviewed block counts do not match the original chunk size.

## Risks

- Extending the current single-table job model too casually could create ambiguous compatibility behavior if old `status` semantics are only partially retired.
- If primary and enhancement transitions are not explicit, the UI may still regress into showing partial success as generic failure.
- Media preprocessing must be bounded and observable; otherwise large-file jobs will simply move the opacity from upload time to preprocessing time.
- Deferring chunked upload is acceptable only if the first-stage UI clearly communicates long upload and processing states.

## Definition of Done

The first-stage redesign is complete when:

- Remote users can still upload whole media files through the current web entry point.
- Jobs expose separate primary and enhancement statuses.
- Draft subtitle output is delivered as the primary success milestone.
- AI review failure no longer causes the entire job to be treated as failed when a draft exists.
- Users can see and download draft artifacts even if enhancement fails.
- The system supports retrying enhancement independently.
- Tests cover staged state behavior and partial-success handling.
