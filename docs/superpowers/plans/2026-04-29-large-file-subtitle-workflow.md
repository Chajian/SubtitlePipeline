# Large File Subtitle Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the web subtitle pipeline so remote whole-file uploads run through staged ingest, preprocessing, primary subtitle generation, and optional enhancement, with draft subtitles delivered before AI review and enhancement failure isolated from primary success.

**Architecture:** Extend the current SQLite-backed web job model with separate primary and enhancement statuses, then split the worker pipeline into draft-first and enhancement phases. Keep `POST /api/jobs` as the upload entrypoint in phase one, but change job orchestration, API payloads, and UI rendering to expose staged progress and partial success cleanly.

**Tech Stack:** Python 3.12, FastAPI, SQLite, static HTML/CSS/JavaScript, `unittest`, `fastapi.testclient`

---

### Task 1: Add failing model and API coverage for staged job statuses

**Files:**
- Modify: `tests/test_webapp_api.py`
- Modify: `webapp/app.py`
- Modify: `webapp/service.py`

- [ ] **Step 1: Write the failing API tests**

```python
    def test_create_job_returns_staged_status_fields(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)

        with patch("webapp.app.WebSettings.from_env", return_value=settings):
            with TestClient(app) as client:
                response = client.post(
                    "/api/jobs",
                    files={"video": ("clip.mp4", b"fake payload", "video/mp4")},
                )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["primary_status"], "uploaded")
        self.assertEqual(payload["enhancement_status"], "pending")
        self.assertEqual(payload["filename"], "clip.mp4")

    def test_job_detail_exposes_primary_and_enhancement_status(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        self._seed_jobs(settings)

        with patch("webapp.app.WebSettings.from_env", return_value=settings):
            with TestClient(app) as client:
                response = client.get("/api/jobs/job-new")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["primary_status"], "completed")
        self.assertEqual(payload["enhancement_status"], "succeeded")
        self.assertIn("current_stage", payload)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_api -v`
Expected: FAIL because the current API still returns the legacy single `status` field and no staged status metadata.

- [ ] **Step 3: Write minimal implementation**

Add staged status mapping in `webapp/service.py` and return staged fields from `webapp/app.py`.

```python
def _legacy_status_to_primary_status(status: str) -> str:
    mapping = {
        "queued": "uploaded",
        "running": "transcribing",
        "succeeded": "completed",
        "failed": "failed",
        "cancelled": "failed",
    }
    return mapping.get(status, "uploaded")
```

```python
return JSONResponse(
    {
        "job_id": job_id,
        "primary_status": "uploaded",
        "enhancement_status": "pending",
        "filename": filename,
        "size_bytes": bytes_written,
    },
    status_code=201,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_api -v`
Expected: PASS with staged status fields present in create and detail responses.

- [ ] **Step 5: Commit**

```bash
git add tests/test_webapp_api.py webapp/app.py webapp/service.py
git commit -m "feat: expose staged web job statuses"
```

### Task 2: Migrate the job store to explicit primary and enhancement fields

**Files:**
- Modify: `webapp/service.py`
- Modify: `tests/test_webapp_api.py`

- [ ] **Step 1: Add failing persistence coverage**

```python
    def test_list_jobs_returns_primary_and_enhancement_status_fields(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        self._seed_jobs(settings)

        with patch("webapp.app.WebSettings.from_env", return_value=settings):
            with TestClient(app) as client:
                response = client.get("/api/jobs")

        self.assertEqual(response.status_code, 200)
        jobs = response.json()
        self.assertIn("primary_status", jobs[0])
        self.assertIn("enhancement_status", jobs[0])
        self.assertIn("current_stage", jobs[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_api.WebAppApiTest.test_list_jobs_returns_primary_and_enhancement_status_fields -v`
Expected: FAIL because `GET /api/jobs` still emits the legacy schema.

- [ ] **Step 3: Implement the schema extension and compatibility layer**

Extend the SQLite-backed job model in `webapp/service.py` with explicit staged fields while preserving old rows.

```python
STAGED_JOB_DEFAULTS = {
    "primary_status": "uploaded",
    "enhancement_status": "pending",
    "current_stage": "uploaded",
    "primary_error_text": None,
    "enhancement_error_text": None,
    "draft_ready_at": None,
    "artifacts_json": "[]",
}
```

```python
def _normalize_job_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["primary_status"] = payload.get("primary_status") or _legacy_status_to_primary_status(payload["status"])
    payload["enhancement_status"] = payload.get("enhancement_status") or _legacy_status_to_enhancement_status(payload["status"])
    payload["current_stage"] = payload.get("current_stage") or payload["primary_status"]
    return payload
```

- [ ] **Step 4: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_api -v`
Expected: PASS with list and detail payloads returning normalized staged fields.

- [ ] **Step 5: Commit**

```bash
git add webapp/service.py tests/test_webapp_api.py
git commit -m "feat: persist staged job metadata"
```

### Task 3: Add preprocessing and draft-first worker stages

**Files:**
- Modify: `auto_subtitle.py`
- Modify: `webapp/service.py`
- Modify: `tests/test_auto_subtitle.py`

- [ ] **Step 1: Write the failing worker tests**

```python
    def test_web_worker_marks_draft_ready_before_ai_review(self) -> None:
        ...
        self.assertEqual(store.get_job(job_id)["primary_status"], "draft_ready")
        self.assertEqual(store.get_job(job_id)["enhancement_status"], "reviewing")

    def test_web_worker_skips_burn_in_primary_web_flow(self) -> None:
        ...
        burn_subtitles.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auto_subtitle -v`
Expected: FAIL because the current pipeline still treats AI review and optional burn steps as part of one linear completion path.

- [ ] **Step 3: Implement minimal draft-first orchestration**

Split the worker orchestration so the web flow can checkpoint after draft creation.

```python
def _write_draft_outputs(...):
    cn_srt = output_dir / f"{stem}.cn.srt"
    segments_to_srt(cn_segments, cn_srt)
    return {"draft_subtitle": cn_srt}
```

```python
if web_progress is not None:
    web_progress.mark_primary_status("draft_ready", current_stage="writing_draft", artifacts=draft_artifacts)

if args.ai_review == "off":
    web_progress.mark_completed(enhancement_status="skipped")
    return
```

- [ ] **Step 4: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auto_subtitle -v`
Expected: PASS with draft-first checkpointing and burn-in excluded from the main web flow.

- [ ] **Step 5: Commit**

```bash
git add auto_subtitle.py webapp/service.py tests/test_auto_subtitle.py
git commit -m "feat: add draft-first web subtitle workflow"
```

### Task 4: Isolate enhancement failures from primary success

**Files:**
- Modify: `subtitle/ai_review.py`
- Modify: `auto_subtitle.py`
- Modify: `tests/test_ai_review.py`
- Modify: `tests/test_auto_subtitle.py`

- [ ] **Step 1: Write the failing tests for enhancement failure isolation**

```python
    def test_ai_review_block_mismatch_marks_enhancement_failed_without_losing_draft(self) -> None:
        ...
        self.assertEqual(job["primary_status"], "draft_ready")
        self.assertEqual(job["enhancement_status"], "failed")
        self.assertIn("expected 80 reviewed blocks, got 79", job["enhancement_error_text"])

    def test_draft_artifacts_remain_available_after_enhancement_failure(self) -> None:
        ...
        self.assertIn("draft_subtitle", {item["kind"] for item in job["files"]})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_ai_review tests.test_auto_subtitle -v`
Expected: FAIL because enhancement exceptions currently abort the full pipeline.

- [ ] **Step 3: Implement enhancement isolation**

Wrap the enhancement stage in `auto_subtitle.py` so AI review exceptions downgrade enhancement only after a draft exists.

```python
try:
    reviewed_path, review_used = maybe_review_bilingual_srt(...)
except Exception as exc:
    if draft_artifacts:
        web_progress.mark_enhancement_failed(str(exc))
        print(f"\033[33m[warn]\033[0m AI review failed after draft generation: {exc}")
        return
    raise
```

Keep strict validation inside `subtitle/ai_review.py`; change orchestration, not the validator.

- [ ] **Step 4: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_ai_review tests.test_auto_subtitle -v`
Expected: PASS with draft artifacts preserved and enhancement failure recorded separately.

- [ ] **Step 5: Commit**

```bash
git add subtitle/ai_review.py auto_subtitle.py tests/test_ai_review.py tests/test_auto_subtitle.py
git commit -m "feat: isolate subtitle enhancement failures"
```

### Task 5: Add enhancement-only retry support

**Files:**
- Modify: `webapp/app.py`
- Modify: `webapp/service.py`
- Modify: `tests/test_webapp_api.py`

- [ ] **Step 1: Write the failing retry test**

```python
    def test_retry_enhancement_requeues_review_without_rerunning_primary(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        self._seed_partial_success_job(settings)

        with patch("webapp.app.WebSettings.from_env", return_value=settings):
            with TestClient(app) as client:
                response = client.post("/api/jobs/job-review-failed/retry-enhancement")

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["enhancement_status"], "pending")
        self.assertEqual(payload["primary_status"], "draft_ready")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_api.WebAppApiTest.test_retry_enhancement_requeues_review_without_rerunning_primary -v`
Expected: FAIL because the endpoint does not exist.

- [ ] **Step 3: Implement the endpoint and queue transition**

```python
@app.post("/api/jobs/{job_id}/retry-enhancement", status_code=202)
async def retry_enhancement(job_id: str, request: Request) -> dict[str, object]:
    job = _runtime(request).retry_enhancement(job_id)
    return {
        "job_id": job_id,
        "primary_status": job["primary_status"],
        "enhancement_status": job["enhancement_status"],
    }
```

```python
def retry_enhancement(self, job_id: str) -> dict[str, Any]:
    # Verify draft artifact exists, reset enhancement state, enqueue enhancement-only work.
    ...
```

- [ ] **Step 4: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_api -v`
Expected: PASS with retry behavior limited to enhancement state.

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py webapp/service.py tests/test_webapp_api.py
git commit -m "feat: add enhancement retry api"
```

### Task 6: Update the web UI for staged and partial-success rendering

**Files:**
- Modify: `webapp/index.html`
- Modify: `tests/test_webapp_bootstrap.py`

- [ ] **Step 1: Add failing frontend contract tests**

```python
    def test_web_index_mentions_draft_ready_and_review_failed_states(self) -> None:
        from webapp.app import app

        with TestClient(app) as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("初稿已生成，可下载", response.text)
        self.assertIn("AI 校对失败，初稿仍可下载", response.text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_bootstrap -v`
Expected: FAIL because the current UI only knows the legacy single-status model.

- [ ] **Step 3: Implement staged rendering and messaging**

Add helpers and labels in `webapp/index.html`.

```javascript
function renderCompositeStatus(job) {
  if (job.primary_status === "draft_ready" && job.enhancement_status === "failed") {
    return "AI 校对失败，初稿仍可下载";
  }
  if (job.primary_status === "draft_ready") {
    return "初稿已生成，可下载";
  }
  return job.current_stage || job.primary_status;
}
```

```javascript
const terminalPrimaryStatuses = ["draft_ready", "completed", "failed"];
```

Update list badges, detail rows, and stage messages to use `primary_status`, `enhancement_status`, and `current_stage`.

- [ ] **Step 4: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_bootstrap -v`
Expected: PASS with staged UI contract text present.

- [ ] **Step 5: Commit**

```bash
git add webapp/index.html tests/test_webapp_bootstrap.py
git commit -m "feat: render staged subtitle job states"
```

### Task 7: Verify integrated staged workflow behavior

**Files:**
- Modify: `tests/test_webapp_api.py`
- Modify: `tests/test_webapp_bootstrap.py`
- Modify: `tests/test_auto_subtitle.py`
- Modify: `tests/test_ai_review.py`

- [ ] **Step 1: Run focused web and worker suites**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_api tests.test_webapp_bootstrap tests.test_auto_subtitle tests.test_ai_review -v`
Expected: PASS with staged statuses, draft-first behavior, and enhancement-failure isolation covered.

- [ ] **Step 2: Run the full test suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: PASS with zero failures.

- [ ] **Step 3: Smoke-check live staged endpoints**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/public/status
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/jobs
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/
```

Expected: HTTP 200 for all three routes and staged status fields in `/api/jobs`.

- [ ] **Step 4: Manual partial-success smoke test**

Run:

```powershell
curl.exe -F "video=@C:\path\to\sample.mp4" http://127.0.0.1:8000/api/jobs
```

Expected: job enters `uploaded`, then `transcribing`, then `draft_ready`; if AI review fails, draft artifacts remain downloadable.

- [ ] **Step 5: Commit**

```bash
git add tests/test_webapp_api.py tests/test_webapp_bootstrap.py tests/test_auto_subtitle.py tests/test_ai_review.py webapp/app.py webapp/index.html webapp/service.py auto_subtitle.py subtitle/ai_review.py
git commit -m "test: verify staged large-file subtitle workflow"
```

## Spec Coverage Check

- Remote users still upload whole files through the existing web entrypoint: covered by Tasks 1, 2, and 7.
- Separate primary and enhancement status modeling: covered by Tasks 1 and 2.
- Draft subtitle output as the primary success milestone: covered by Task 3.
- AI review failure no longer invalidates a usable draft: covered by Task 4.
- Independent enhancement retry: covered by Task 5.
- UI and API support for staged and partial success: covered by Tasks 1, 2, 5, and 6.
- Later chunked upload intentionally deferred: reflected in the task scope; no implementation task included.

## Placeholder Scan

- No `TBD`, `TODO`, or deferred implementation placeholders remain in the plan steps.
- Each code-changing task names concrete files, commands, and expected behavior.
- Retry and staged-state names are consistent across plan sections.

## Type Consistency Check

- Status fields use `primary_status`, `enhancement_status`, and `current_stage` consistently.
- Partial success is consistently represented as `primary_status = draft_ready` and `enhancement_status = failed`.
- Retry route name is consistently `POST /api/jobs/{job_id}/retry-enhancement`.
- Draft artifacts are consistently described with kinds such as `draft_subtitle` and `draft_text`.
