from __future__ import annotations

import json
import marshal
import sqlite3
from pathlib import Path
from typing import Any


def _load_compiled_module() -> None:
    pyc_path = Path(__file__).with_name("service.compiled.pyc")
    if not pyc_path.exists():
        raise ImportError(f"Missing compiled web service module: {pyc_path}")

    with pyc_path.open("rb") as file_obj:
        file_obj.read(16)
        code = marshal.load(file_obj)

    module_globals = {
        "__builtins__": __builtins__,
        "__file__": __file__,
        "__name__": __name__,
        "__package__": __package__,
    }
    exec(code, module_globals)
    globals().update(module_globals)


_load_compiled_module()


_STAGED_COLUMNS = ("primary_status", "enhancement_status", "current_stage")
_LEGACY_INIT = JobStore.__init__
_LEGACY_BUILD_CLI_COMMAND = build_cli_command
_LEGACY_CREATE_JOB = JobStore.create_job
_LEGACY_CLAIM_NEXT_JOB = JobStore.claim_next_job
_LEGACY_COMPLETE_JOB = JobStore.complete_job
_LEGACY_FAIL_JOB = JobStore.fail_job
_LEGACY_GET_JOB = JobStore.get_job

_LEGACY_STATUS_MAPPING = {
    "queued": {
        "primary_status": "uploaded",
        "enhancement_status": "pending",
        "current_stage": "uploaded",
    },
    "running": {
        "primary_status": "transcribing",
        "enhancement_status": "pending",
        "current_stage": "transcribing",
    },
    "succeeded": {
        "primary_status": "completed",
        "enhancement_status": "succeeded",
        "current_stage": "completed",
    },
    "failed": {
        "primary_status": "failed",
        "enhancement_status": "pending",
        "current_stage": "failed",
    },
}


def _staged_status_fields(job: dict[str, Any]) -> dict[str, str]:
    status = str(job.get("status") or "")
    default = {
        "primary_status": "uploaded",
        "enhancement_status": "pending",
        "current_stage": "uploaded",
    }
    return dict(_LEGACY_STATUS_MAPPING.get(status, default))


def _with_staged_status(job: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    payload = dict(job)
    canonical = _LEGACY_STATUS_MAPPING.get(str(payload.get("status") or ""))
    repaired = False
    if canonical is not None:
        repaired = any(payload.get(field) != canonical[field] for field in _STAGED_COLUMNS)
        payload.update(canonical)
        return payload, repaired

    if payload.get("primary_status") in (None, ""):
        payload["primary_status"] = _staged_status_fields(payload)["primary_status"]
        repaired = True
    if payload.get("enhancement_status") in (None, ""):
        payload["enhancement_status"] = _staged_status_fields(payload)["enhancement_status"]
        repaired = True
    if payload.get("current_stage") in (None, ""):
        payload["current_stage"] = payload["primary_status"]
        repaired = True
    return payload, repaired


def _job_store_init(self: "JobStore", settings: "WebSettings") -> None:
    _LEGACY_INIT(self, settings)
    _ensure_staged_columns(self)


def _ensure_staged_columns(self: "JobStore") -> None:
    if getattr(self, "_staged_columns_ready", False):
        return

    conn = sqlite3.connect(self.settings.db_path)
    try:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(jobs)")
        }
        for column in _STAGED_COLUMNS:
            if column not in existing:
                try:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} TEXT")
                except sqlite3.OperationalError as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise
        conn.execute(
            """
            UPDATE jobs
            SET
                primary_status = CASE
                    WHEN primary_status IS NULL OR primary_status = '' THEN
                        CASE status
                            WHEN 'queued' THEN 'uploaded'
                            WHEN 'running' THEN 'transcribing'
                            WHEN 'succeeded' THEN 'completed'
                            WHEN 'failed' THEN 'failed'
                            ELSE 'uploaded'
                        END
                    ELSE primary_status
                END,
                enhancement_status = CASE
                    WHEN enhancement_status IS NULL OR enhancement_status = '' THEN
                        CASE status
                            WHEN 'succeeded' THEN 'succeeded'
                            ELSE 'pending'
                        END
                    ELSE enhancement_status
                END,
                current_stage = CASE
                    WHEN current_stage IS NULL OR current_stage = '' THEN
                        COALESCE(
                            NULLIF(primary_status, ''),
                            CASE status
                                WHEN 'queued' THEN 'uploaded'
                                WHEN 'running' THEN 'transcribing'
                                WHEN 'succeeded' THEN 'completed'
                                WHEN 'failed' THEN 'failed'
                                ELSE 'uploaded'
                            END
                        )
                    ELSE current_stage
                END
            """
        )
        conn.commit()
    finally:
        conn.close()

    self._staged_columns_ready = True


def _persisted_staged_columns(self: "JobStore", job_id: str) -> dict[str, Any]:
    _ensure_staged_columns(self)
    conn = sqlite3.connect(self.settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT primary_status, enhancement_status, current_stage
            FROM jobs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {}
    return dict(row)


def _update_staged_columns(self: "JobStore", job_id: str, values: dict[str, str]) -> None:
    _ensure_staged_columns(self)
    assignments = ", ".join(f"{column} = ?" for column in values)
    params = [values[column] for column in values]
    params.append(job_id)

    conn = sqlite3.connect(self.settings.db_path)
    try:
        conn.execute(
            f"UPDATE jobs SET {assignments} WHERE job_id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def _runtime_state_path(self: "JobStore", job_id: str) -> Path:
    return self.settings.jobs_dir / job_id / "job-state.json"


def _progress_artifact(path: Path, kind: str) -> dict[str, str]:
    return {
        "name": path.name,
        "kind": kind,
        "status": "ready",
    }


def _write_runtime_state(self: "JobStore", job_id: str, payload: dict[str, Any]) -> None:
    path = _runtime_state_path(self, job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_runtime_state(self: "JobStore", job_id: str) -> dict[str, Any]:
    path = _runtime_state_path(self, job_id)
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _best_effort_update_staged_columns(self: "JobStore", job_id: str, values: dict[str, str]) -> None:
    try:
        _update_staged_columns(self, job_id, values)
    except sqlite3.Error:
        pass


def _best_effort_persisted_staged_columns(self: "JobStore", job_id: str) -> dict[str, Any]:
    try:
        return _persisted_staged_columns(self, job_id)
    except sqlite3.Error:
        return {}


def _normalize_job_payload(self: "JobStore", job: dict[str, Any]) -> dict[str, Any]:
    payload, repaired = _with_staged_status(job)
    if job.get("job_id"):
        runtime_state = _read_runtime_state(self, str(job["job_id"]))
        for key in (
            "primary_status",
            "enhancement_status",
            "current_stage",
            "primary_error_text",
            "enhancement_error_text",
            "artifacts",
        ):
            if key in runtime_state:
                payload[key] = runtime_state[key]
    if repaired and job.get("job_id"):
        _best_effort_update_staged_columns(
            self,
            str(job["job_id"]),
            {field: payload[field] for field in _STAGED_COLUMNS},
        )
    return payload


def _create_job(self: "JobStore", **kwargs: Any) -> None:
    _LEGACY_CREATE_JOB(self, **kwargs)
    _best_effort_update_staged_columns(
        self,
        kwargs["job_id"],
        {
            "primary_status": "uploaded",
            "enhancement_status": "pending",
            "current_stage": "uploaded",
        },
    )


def _build_cli_command(
    settings: "WebSettings",
    upload_path: Path,
    output_dir: Path,
    options: dict[str, Any],
) -> list[str]:
    command = list(_LEGACY_BUILD_CLI_COMMAND(settings, upload_path, output_dir, options))
    if "--no-burn" not in command:
        command.append("--no-burn")
    progress_path = output_dir.parent / "job-state.json"
    command.extend(["--web-progress-file", str(progress_path)])
    if options.get("__retry_enhancement"):
        command.append("--retry-enhancement")
    return command


def _retry_enhancement(self: "JobStore", job_id: str) -> dict[str, Any]:
    job = _get_job(self, job_id)
    if job is None:
        raise WebJobError("job not found")

    output_dir = Path(str(job["output_dir"]))
    cn_srt = output_dir / f"{output_dir.parent.name}.cn.srt"
    bilingual_srt = output_dir / f"{output_dir.parent.name}.bilingual.srt"
    if not cn_srt.exists():
        raise WebJobError("draft subtitle not found")

    options = dict(job.get("options") or {})
    options["ai_review"] = True
    options["__retry_enhancement"] = True

    conn = sqlite3.connect(self.settings.db_path)
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'queued',
                options_json = ?,
                error_text = NULL,
                exit_code = NULL,
                started_at = NULL,
                completed_at = NULL
            WHERE job_id = ?
            """,
            (json.dumps(options, ensure_ascii=False), job_id),
        )
        conn.commit()
    finally:
        conn.close()

    _best_effort_update_staged_columns(
        self,
        job_id,
        {
            "primary_status": "draft_ready",
            "enhancement_status": "pending",
            "current_stage": "draft_ready",
        },
    )
    artifacts = [_progress_artifact(cn_srt, "draft_subtitle")]
    en_srt = output_dir / f"{output_dir.parent.name}.en.srt"
    if en_srt.exists():
        artifacts.append(_progress_artifact(en_srt, "draft_translation"))
    if bilingual_srt.exists():
        artifacts.append(_progress_artifact(bilingual_srt, "draft_bilingual_subtitle"))
    _write_runtime_state(
        self,
        job_id,
        {
            "primary_status": "draft_ready",
            "enhancement_status": "pending",
            "current_stage": "draft_ready",
            "artifacts": artifacts,
            "primary_error_text": None,
            "enhancement_error_text": None,
        },
    )
    return _get_job(self, job_id) or {"job_id": job_id}


def _complete_job(self: "JobStore", job_id: str, *, exit_code: int) -> None:
    _LEGACY_COMPLETE_JOB(self, job_id, exit_code=exit_code)
    _best_effort_update_staged_columns(
        self,
        job_id,
        {
            "primary_status": "completed",
            "enhancement_status": "succeeded",
            "current_stage": "completed",
        },
    )


def _claim_next_job(self: "JobStore") -> dict[str, Any] | None:
    claimed = _LEGACY_CLAIM_NEXT_JOB(self)
    if claimed is None:
        return None

    job_id = str(claimed["job_id"])
    _best_effort_update_staged_columns(
        self,
        job_id,
        {
            "primary_status": "transcribing",
            "enhancement_status": "pending",
            "current_stage": "transcribing",
        },
    )
    payload = dict(claimed)
    payload.update(_best_effort_persisted_staged_columns(self, job_id))
    return _normalize_job_payload(self, payload)


def _fail_job(self: "JobStore", job_id: str, *, error_text: str, exit_code: int | None = None) -> None:
    _LEGACY_FAIL_JOB(self, job_id, error_text=error_text, exit_code=exit_code)
    _best_effort_update_staged_columns(
        self,
        job_id,
        {
            "primary_status": "failed",
            "enhancement_status": "pending",
            "current_stage": "failed",
        },
    )


def _get_job(self: "JobStore", job_id: str) -> dict[str, Any] | None:
    job = _LEGACY_GET_JOB(self, job_id)
    if job is None:
        return None
    payload = dict(job)
    payload.update(_persisted_staged_columns(self, job_id))
    return _normalize_job_payload(self, payload)


def _list_jobs(self: "JobStore", limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, int(limit))
    _ensure_staged_columns(self)
    conn = sqlite3.connect(self.settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                job_id,
                status,
                original_filename,
                exit_code,
                created_at,
                started_at,
                completed_at,
                primary_status,
                enhancement_status,
                current_stage
            FROM jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    return [_normalize_job_payload(self, dict(row)) for row in rows]


JobStore.__init__ = _job_store_init
build_cli_command = _build_cli_command
JobWorker._execute_job.__globals__["build_cli_command"] = _build_cli_command
JobStore.create_job = _create_job
JobStore.claim_next_job = _claim_next_job
JobStore.complete_job = _complete_job
JobStore.fail_job = _fail_job
JobStore.get_job = _get_job
JobStore.list_jobs = _list_jobs
JobStore.retry_enhancement = _retry_enhancement
