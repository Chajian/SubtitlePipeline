# Subtitle Debug Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a practical debug and observability system to the subtitle pipeline so web jobs retain compact diagnostic evidence by default, CLI runs can opt into full diagnostics with `--debug`, and failures like AI chunk mismatches can be diagnosed from saved artifacts instead of guessed from coarse logs.

**Architecture:** Introduce a small debug writer layer that emits a per-run manifest, timeline, stage summaries, and targeted AI chunk evidence. Thread it through `auto_subtitle.py` and the AI review helpers, then extend web job retention logic so successful diagnostics follow the normal TTL and failed or partial-success diagnostics survive longer.

**Tech Stack:** Python 3.12, FastAPI web runtime, SQLite-backed web jobs, filesystem artifact retention, static HTML already out of scope, `unittest`

---

### Task 1: Add failing coverage and scaffolding for diagnostic artifacts

**Files:**
- Create: `subtitle/debug_trace.py`
- Modify: `tests/test_auto_subtitle.py`
- Modify: `tests/test_ai_review.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_debug_trace_writes_manifest_and_timeline_for_web_mode(self) -> None:
    temp_dir = self._make_temp_dir()
    trace_root = temp_dir / "output" / "debug"

    from subtitle.debug_trace import DebugTrace

    trace = DebugTrace(mode="web_compact", root=trace_root, enabled=True)
    trace.write_manifest({"job_id": "job-1", "result": "completed"})
    trace.append_timeline({"stage": "transcribe", "event": "started"})

    self.assertTrue((trace_root / "manifest.json").exists())
    self.assertTrue((trace_root / "timeline.jsonl").exists())

def test_debug_trace_skips_disk_writes_when_disabled(self) -> None:
    temp_dir = self._make_temp_dir()
    trace_root = temp_dir / "output" / "debug"

    from subtitle.debug_trace import DebugTrace

    trace = DebugTrace(mode="cli_default", root=trace_root, enabled=False)
    trace.write_manifest({"job_id": "job-1"})

    self.assertFalse(trace_root.exists())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auto_subtitle tests.test_ai_review -v`
Expected: FAIL because `subtitle.debug_trace` does not exist yet.

- [ ] **Step 3: Write the minimal debug trace helper**

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DebugTrace:
    mode: str
    root: Path
    enabled: bool = True

    def write_manifest(self, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append_timeline(self, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "timeline.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Re-run the tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auto_subtitle tests.test_ai_review -v`
Expected: PASS for the new trace helper coverage.

- [ ] **Step 5: Commit**

```bash
git add subtitle/debug_trace.py tests/test_auto_subtitle.py tests/test_ai_review.py
git commit -m "feat: add debug trace scaffolding"
```

### Task 2: Add CLI debug mode and web compact defaults to the main pipeline

**Files:**
- Modify: `auto_subtitle.py`
- Modify: `webapp/service.py`
- Modify: `tests/test_auto_subtitle.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_cli_command_enables_web_compact_debug_for_web_jobs(self) -> None:
    temp_dir = self._make_temp_dir()
    settings = WebSettings.from_env(temp_dir)
    command = build_cli_command(
        settings,
        temp_dir / "input.mp4",
        temp_dir / "jobs" / "job-1" / "output",
        {"model": "medium", "zh_script": "simplified", "burn_subtitles": True, "ai_review": True},
    )

    self.assertIn("--debug-mode", command)
    self.assertIn("web_compact", command)

def test_parse_args_accepts_cli_debug_mode(self) -> None:
    with patch("sys.argv", ["auto_subtitle.py", "input.mp4", "--debug"]):
        args = auto_subtitle.parse_args()

    self.assertTrue(args.debug)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auto_subtitle -v`
Expected: FAIL because the CLI has no debug-mode flags and web commands do not inject them.

- [ ] **Step 3: Add CLI arguments and command wiring**

```python
parser.add_argument("--debug", action="store_true", help="Write full diagnostic artifacts")
parser.add_argument("--debug-mode", default="cli_default", help=argparse.SUPPRESS)
```

```python
if debug_enabled:
    trace = DebugTrace(mode=args.debug_mode, root=output_dir / "debug", enabled=True)
else:
    trace = DebugTrace(mode=args.debug_mode, root=output_dir / "debug", enabled=False)
```

```python
command.extend(["--debug-mode", "web_compact"])
```

- [ ] **Step 4: Re-run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auto_subtitle -v`
Expected: PASS with CLI debug flag parsing and web command injection verified.

- [ ] **Step 5: Commit**

```bash
git add auto_subtitle.py webapp/service.py tests/test_auto_subtitle.py
git commit -m "feat: wire debug mode through web and cli"
```

### Task 3: Emit stage summaries and timeline events for the full pipeline

**Files:**
- Modify: `subtitle/debug_trace.py`
- Modify: `auto_subtitle.py`
- Modify: `tests/test_auto_subtitle.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_web_debug_trace_writes_stage_summaries_for_successful_pipeline(self) -> None:
    temp_dir = self._make_temp_dir()
    progress_path = temp_dir / "job-state.json"
    output_dir = temp_dir / "output"
    ...
    auto_subtitle.main()

    debug_root = output_dir / "debug"
    self.assertTrue((debug_root / "stages" / "transcribe.json").exists())
    self.assertTrue((debug_root / "timeline.jsonl").exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auto_subtitle -v`
Expected: FAIL because the pipeline does not currently emit stage summary files.

- [ ] **Step 3: Extend the trace helper and instrument the pipeline**

```python
def write_stage_summary(self, stage: str, payload: dict[str, Any]) -> None:
    if not self.enabled:
        return
    stage_dir = self.root / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / f"{stage}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

```python
trace.append_timeline({"stage": "transcribe", "event": "started", "status": "running"})
...
trace.write_stage_summary(
    "transcribe",
    {
        "stage": "transcribe",
        "status": "completed",
        "input_count": 1,
        "output_count": len(cn_segments),
    },
)
```

- [ ] **Step 4: Re-run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auto_subtitle -v`
Expected: PASS with stage summaries and timeline output present.

- [ ] **Step 5: Commit**

```bash
git add subtitle/debug_trace.py auto_subtitle.py tests/test_auto_subtitle.py
git commit -m "feat: add stage debug summaries"
```

### Task 4: Capture failed AI chunk request and response evidence

**Files:**
- Modify: `subtitle/ai_review.py`
- Modify: `subtitle/debug_trace.py`
- Modify: `tests/test_ai_review.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_failed_review_chunk_writes_request_response_and_error_artifacts(self) -> None:
    temp_dir = self._make_temp_dir()
    debug_root = temp_dir / "output" / "debug"
    settings = AIReviewSettings(provider="siliconflow")
    ...
    with self.assertRaisesRegex(ValueError, "expected 1 reviewed blocks"):
        review_text_blocks(original_blocks, settings, trace=trace)

    self.assertTrue((debug_root / "ai-review" / "chunk-01.request.json").exists())
    self.assertTrue((debug_root / "ai-review" / "chunk-01.response.txt").exists())
    self.assertTrue((debug_root / "ai-review" / "chunk-01.error.json").exists())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_ai_review -v`
Expected: FAIL because AI review code does not accept a trace object or emit chunk evidence.

- [ ] **Step 3: Thread trace support into AI review helpers**

```python
def write_chunk_artifact(self, category: str, chunk_index: int, suffix: str, payload: str | dict[str, Any]) -> None:
    ...
```

```python
trace.write_chunk_artifact("ai-review", chunk_index, "request.json", request_payload)
trace.write_chunk_artifact("ai-review", chunk_index, "response.txt", raw_response)
trace.write_chunk_artifact(
    "ai-review",
    chunk_index,
    "error.json",
    {"error_code": "ai_review_block_count_mismatch", "error_message": str(exc)},
)
```

- [ ] **Step 4: Re-run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_ai_review -v`
Expected: PASS with failed chunk evidence written on mismatch.

- [ ] **Step 5: Commit**

```bash
git add subtitle/ai_review.py subtitle/debug_trace.py tests/test_ai_review.py
git commit -m "feat: retain failed ai chunk evidence"
```

### Task 5: Add machine-readable error codes and fallback diagnostics

**Files:**
- Modify: `subtitle/ai_review.py`
- Modify: `auto_subtitle.py`
- Modify: `tests/test_ai_review.py`
- Modify: `tests/test_auto_subtitle.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_ai_review_failure_writes_machine_readable_error_code(self) -> None:
    ...
    payload = json.loads((debug_root / "ai-review" / "chunk-01.error.json").read_text(encoding="utf-8"))
    self.assertEqual(payload["error_code"], "ai_review_block_count_mismatch")

def test_translation_fallback_appends_timeline_event(self) -> None:
    ...
    timeline = (output_dir / "debug" / "timeline.jsonl").read_text(encoding="utf-8")
    self.assertIn("translation_fallback_triggered", timeline)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_ai_review tests.test_auto_subtitle -v`
Expected: FAIL because error codes and fallback events are not yet explicit.

- [ ] **Step 3: Add error-code helpers and timeline events**

```python
ERROR_AI_REVIEW_BLOCK_COUNT_MISMATCH = "ai_review_block_count_mismatch"
ERROR_TRANSLATION_FALLBACK_TRIGGERED = "translation_fallback_triggered"
```

```python
trace.append_timeline(
    {
        "stage": "translate_reviewed",
        "event": "translation_fallback_triggered",
        "status": "degraded",
    }
)
```

- [ ] **Step 4: Re-run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_ai_review tests.test_auto_subtitle -v`
Expected: PASS with error codes and fallback diagnostics present.

- [ ] **Step 5: Commit**

```bash
git add subtitle/ai_review.py auto_subtitle.py tests/test_ai_review.py tests/test_auto_subtitle.py
git commit -m "feat: add machine readable debug errors"
```

### Task 6: Implement compact retention for web diagnostics

**Files:**
- Modify: `webapp/service.py`
- Modify: `tests/test_webapp_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_cleanup_expired_jobs_keeps_failed_debug_artifacts_longer_than_successful_ones(self) -> None:
    temp_root = self._make_temp_root()
    settings = WebSettings.from_env(temp_root)
    ...
    self.assertFalse(success_debug_dir.exists())
    self.assertTrue(failed_debug_dir.exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_api -v`
Expected: FAIL because cleanup currently treats only the core job directories and has no differentiated debug retention.

- [ ] **Step 3: Extend cleanup behavior**

```python
success_debug_ttl = timedelta(hours=24)
failed_debug_ttl = timedelta(hours=72)
```

```python
if debug_dir.exists():
    if status == "succeeded" and completed_at < success_cutoff:
        shutil.rmtree(debug_dir, ignore_errors=True)
    elif status in {"failed", "partial_success"} and completed_at < failed_cutoff:
        shutil.rmtree(debug_dir, ignore_errors=True)
```

- [ ] **Step 4: Re-run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_webapp_api -v`
Expected: PASS with differentiated debug-retention cleanup.

- [ ] **Step 5: Commit**

```bash
git add webapp/service.py tests/test_webapp_api.py
git commit -m "feat: retain debug artifacts by outcome"
```

### Task 7: Verify the full observability slice

**Files:**
- Modify: `tests/test_auto_subtitle.py`
- Modify: `tests/test_ai_review.py`
- Modify: `tests/test_webapp_api.py`

- [ ] **Step 1: Run the focused observability suites**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auto_subtitle tests.test_ai_review tests.test_webapp_api -v`
Expected: PASS with stage summaries, failed AI chunk evidence, error codes, and retention behavior covered.

- [ ] **Step 2: Run the full test suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: PASS with zero failures.

- [ ] **Step 3: Manual smoke-check a compact web diagnostic run**

Run:

```powershell
curl.exe -F "video=@D:\workspace\project\ai\subtitle-pipeline\2026-03-08 20-45-26.mp4" `
  -F "model=medium" `
  -F "zh_script=simplified" `
  -F "burn_subtitles=on" `
  -F "ai_review=on" `
  http://127.0.0.1:8000/api/jobs
```

Expected:

- Job output directory contains `debug/manifest.json`
- `debug/timeline.jsonl` exists
- if AI review fails, failed chunk request/response artifacts exist under `debug/ai-review/`

- [ ] **Step 4: Commit**

```bash
git add subtitle/debug_trace.py auto_subtitle.py subtitle/ai_review.py webapp/service.py tests/test_auto_subtitle.py tests/test_ai_review.py tests/test_webapp_api.py
git commit -m "test: verify subtitle debug observability"
```

## Spec Coverage Check

- Full-pipeline stage diagnostics: covered by Tasks 2 and 3.
- Web default compact diagnostics: covered by Tasks 2 and 6.
- CLI `--debug` full diagnostics: covered by Task 2.
- Failed AI chunk evidence: covered by Task 4.
- Machine-readable error codes: covered by Task 5.
- Retention policy differences by outcome: covered by Task 6.
- Diagnosing `expected 80 reviewed blocks, got 79` from retained evidence: covered by Tasks 4, 5, and 7.

## Placeholder Scan

- No `TBD`, `TODO`, or deferred implementation placeholders remain.
- Every task names exact files, commands, and expected outcomes.
- Debug artifact filenames and error-code identifiers are concrete.

## Type Consistency Check

- Debug root consistently uses `output/debug/`.
- Timeline file is consistently `timeline.jsonl`.
- Stage summaries consistently live under `output/debug/stages/`.
- Failed AI chunk evidence consistently lives under `output/debug/ai-review/`.
- Error-code naming consistently uses snake-case strings such as `ai_review_block_count_mismatch`.
