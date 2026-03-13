"""Runtime services for the public web shell."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi"}
MODEL_CHOICES = {"small", "medium", "large-v3"}
ZH_SCRIPT_CHOICES = {"simplified", "traditional"}


class WebJobError(RuntimeError):
    """Base error for web job operations."""


class QuotaExceededError(WebJobError):
    """Raised when the global anonymous quota is exhausted."""


class QueueFullError(WebJobError):
    """Raised when the local queue is full."""


class InvalidJobOptionsError(WebJobError):
    """Raised when the submitted job options are invalid."""


@dataclass(slots=True)
class WebSettings:
    """Runtime settings for the web shell."""

    root_dir: Path
    data_dir: Path
    db_path: Path
    uploads_dir: Path
    jobs_dir: Path
    timezone_name: str
    daily_quota: int
    max_upload_mb: int
    max_queue_size: int
    job_timeout_seconds: int
    result_ttl_hours: int
    host: str
    port: int

    @classmethod
    def from_env(cls, root_dir: Path) -> WebSettings:
        data_dir = Path(os.getenv("WEB_DATA_DIR", root_dir / "web_data"))
        return cls(
            root_dir=root_dir,
            data_dir=data_dir,
            db_path=data_dir / "app.db",
            uploads_dir=data_dir / "uploads",
            jobs_dir=data_dir / "jobs",
            timezone_name=os.getenv("WEB_TIMEZONE", "Asia/Shanghai"),
            daily_quota=int(os.getenv("WEB_DAILY_QUOTA", "100")),
            max_upload_mb=int(os.getenv("WEB_MAX_UPLOAD_MB", "200")),
            max_queue_size=int(os.getenv("WEB_MAX_QUEUE_SIZE", "20")),
            job_timeout_seconds=int(os.getenv("WEB_JOB_TIMEOUT_SECONDS", str(45 * 60))),
            result_ttl_hours=int(os.getenv("WEB_RESULT_TTL_HOURS", "24")),
            host=os.getenv("WEB_HOST", "0.0.0.0"),
            port=int(os.getenv("WEB_PORT", "8000")),
        )

    @property
    def timezone(self) -> ZoneInfo | timezone:
        try:
            return ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError:
            if self.timezone_name == "Asia/Shanghai":
                return timezone(timedelta(hours=8), name="Asia/Shanghai")
            return timezone.utc


def validate_job_options(options: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize UI-submitted job options."""
    model = str(options.get("model", "medium")).strip().lower()
    if model not in MODEL_CHOICES:
        raise InvalidJobOptionsError(f"unsupported model: {model}")

    zh_script = str(options.get("zh_script", "simplified")).strip().lower()
    if zh_script not in ZH_SCRIPT_CHOICES:
        raise InvalidJobOptionsError(f"unsupported Chinese script: {zh_script}")

    burn_subtitles = bool(options.get("burn_subtitles", False))
    ai_review = bool(options.get("ai_review", False))

    return {
        "model": model,
        "zh_script": zh_script,
        "burn_subtitles": burn_subtitles,
        "ai_review": ai_review,
    }


def build_cli_command(
    settings: WebSettings,
    upload_path: Path,
    output_dir: Path,
    options: dict[str, Any],
) -> list[str]:
    """Build the CLI command used by the web worker."""
    normalized = validate_job_options(options)
    command = [
        sys.executable,
        str(settings.root_dir / "auto_subtitle.py"),
        str(upload_path),
        "--output",
        str(output_dir),
        "--model",
        normalized["model"],
        "--source-language",
        "zh",
        "--zh-script",
        normalized["zh_script"],
        "--ai-review",
        "on" if normalized["ai_review"] else "off",
    ]
    if not normalized["burn_subtitles"]:
        command.append("--no-burn")
    return command


def make_job_id() -> str:
    """Create a short opaque job identifier."""
    return uuid4().hex[:12]


def tail_text_file(path: Path, max_chars: int = 8_000) -> str:
    """Read the tail of a UTF-8 text file."""
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def list_job_files(job_id: str, output_dir: Path) -> list[dict[str, Any]]:
    """Describe downloadable files for a completed job."""
    if not output_dir.exists():
        return []

    files: list[dict[str, Any]] = []
    for path in sorted(output_dir.iterdir()):
        if not path.is_file():
            continue
        files.append(
            {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "url": f"/api/jobs/{job_id}/files/{path.name}",
            }
        )
    return files


class JobStore:
    """SQLite-backed store for jobs and quota usage."""

    def __init__(self, settings: WebSettings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.settings.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _now(self) -> datetime:
        return datetime.now(self.settings.timezone)

    def _today_key(self) -> str:
        return self._now().date().isoformat()

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS daily_usage (
                    usage_day TEXT PRIMARY KEY,
                    used_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    upload_path TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    log_path TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    error_text TEXT,
                    exit_code INTEGER,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );
                """
            )

    def get_public_status(self) -> dict[str, Any]:
        """Return the current public status for the landing page."""
        today = self._today_key()
        with self._connect() as connection:
            usage_row = connection.execute(
                "SELECT used_count FROM daily_usage WHERE usage_day = ?",
                (today,),
            ).fetchone()
            queued_count = connection.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE status = 'queued'"
            ).fetchone()["count"]
            running_count = connection.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE status = 'running'"
            ).fetchone()["count"]

        used_count = int(usage_row["used_count"]) if usage_row else 0
        remaining = max(self.settings.daily_quota - used_count, 0)
        return {
            "date": today,
            "daily_quota": self.settings.daily_quota,
            "used_quota": used_count,
            "remaining_quota": remaining,
            "queue_length": queued_count,
            "running_jobs": running_count,
            "accepting_jobs": remaining > 0 and queued_count < self.settings.max_queue_size,
            "max_upload_mb": self.settings.max_upload_mb,
            "max_queue_size": self.settings.max_queue_size,
        }

    def create_job(
        self,
        *,
        job_id: str,
        original_filename: str,
        upload_path: Path,
        output_dir: Path,
        log_path: Path,
        options: dict[str, Any],
    ) -> None:
        """Reserve quota and create a queued job."""
        normalized_options = validate_job_options(options)
        created_at = self._now().isoformat()
        today = self._today_key()

        with self._lock, self._connect() as connection:
            usage_row = connection.execute(
                "SELECT used_count FROM daily_usage WHERE usage_day = ?",
                (today,),
            ).fetchone()
            used_count = int(usage_row["used_count"]) if usage_row else 0
            if used_count >= self.settings.daily_quota:
                raise QuotaExceededError("today's anonymous quota is exhausted")

            queued_count = connection.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE status = 'queued'"
            ).fetchone()["count"]
            if queued_count >= self.settings.max_queue_size:
                raise QueueFullError("job queue is full")

            connection.execute(
                """
                INSERT INTO daily_usage (usage_day, used_count)
                VALUES (?, 1)
                ON CONFLICT(usage_day) DO UPDATE SET used_count = used_count + 1
                """,
                (today,),
            )
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id,
                    status,
                    original_filename,
                    upload_path,
                    output_dir,
                    log_path,
                    options_json,
                    created_at
                ) VALUES (?, 'queued', ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    original_filename,
                    str(upload_path),
                    str(output_dir),
                    str(log_path),
                    json.dumps(normalized_options),
                    created_at,
                ),
            )

    def claim_next_job(self) -> dict[str, Any] | None:
        """Claim the next queued job for execution."""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None

            started_at = self._now().isoformat()
            connection.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE job_id = ?",
                (started_at, row["job_id"]),
            )
            data = dict(row)
            data["status"] = "running"
            data["started_at"] = started_at
            data["options"] = json.loads(data.pop("options_json"))
            return data

    def complete_job(self, job_id: str, *, exit_code: int) -> None:
        """Mark a job as completed successfully."""
        completed_at = self._now().isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'succeeded',
                    exit_code = ?,
                    error_text = NULL,
                    completed_at = ?
                WHERE job_id = ?
                """,
                (exit_code, completed_at, job_id),
            )

    def fail_job(self, job_id: str, *, error_text: str, exit_code: int | None = None) -> None:
        """Mark a job as failed."""
        completed_at = self._now().isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    exit_code = ?,
                    error_text = ?,
                    completed_at = ?
                WHERE job_id = ?
                """,
                (exit_code, error_text, completed_at, job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Fetch a job record."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None

        data = dict(row)
        options = json.loads(data.pop("options_json"))
        output_dir = Path(data["output_dir"])
        log_path = Path(data["log_path"])
        data["options"] = options
        data["files"] = list_job_files(job_id, output_dir) if data["status"] == "succeeded" else []
        data["log_tail"] = tail_text_file(log_path)
        return data

    def cleanup_expired_jobs(self) -> int:
        """Delete expired files and old job records."""
        cutoff = self._now() - timedelta(hours=self.settings.result_ttl_hours)
        removed = 0

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT job_id, upload_path, output_dir
                FROM jobs
                WHERE status IN ('succeeded', 'failed')
                  AND completed_at IS NOT NULL
                  AND completed_at < ?
                """,
                (cutoff.isoformat(),),
            ).fetchall()

            for row in rows:
                shutil.rmtree(Path(row["output_dir"]).parent, ignore_errors=True)
                upload_path = Path(row["upload_path"])
                if upload_path.exists():
                    upload_path.unlink()
                connection.execute("DELETE FROM jobs WHERE job_id = ?", (row["job_id"],))
                removed += 1

        return removed


class JobWorker:
    """Background worker that executes subtitle jobs serially."""

    def __init__(self, settings: WebSettings, store: JobStore) -> None:
        self.settings = settings
        self.store = store
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="subtitle-web-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        last_cleanup = 0.0
        while not self._stop_event.is_set():
            if time.monotonic() - last_cleanup > 600:
                self.store.cleanup_expired_jobs()
                last_cleanup = time.monotonic()

            job = self.store.claim_next_job()
            if job is None:
                self._stop_event.wait(1.0)
                continue

            try:
                self._execute_job(job)
            except Exception as exc:  # noqa: BLE001
                self.store.fail_job(job["job_id"], error_text=str(exc), exit_code=None)

    def _execute_job(self, job: dict[str, Any]) -> None:
        job_id = job["job_id"]
        upload_path = Path(job["upload_path"])
        output_dir = Path(job["output_dir"])
        log_path = Path(job["log_path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        command = build_cli_command(self.settings, upload_path, output_dir, job["options"])
        with log_path.open("a", encoding="utf-8", errors="replace") as log_handle:
            log_handle.write(f"$ {' '.join(command)}\n\n")
            log_handle.flush()

            process = subprocess.Popen(
                command,
                cwd=self.settings.root_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert process.stdout is not None

            reader = threading.Thread(
                target=self._pump_output,
                args=(process.stdout, log_handle),
                name=f"subtitle-web-job-{job_id}",
                daemon=True,
            )
            reader.start()

            timed_out = False
            try:
                exit_code = process.wait(timeout=self.settings.job_timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                exit_code = process.wait()
                log_handle.write(
                    f"\n[web] Job exceeded timeout ({self.settings.job_timeout_seconds}s) and was terminated.\n"
                )
                log_handle.flush()

            reader.join(timeout=5)

        if timed_out:
            self.store.fail_job(job_id, error_text="job timed out", exit_code=exit_code)
            return

        if exit_code == 0:
            self.store.complete_job(job_id, exit_code=exit_code)
            return

        error_tail = tail_text_file(log_path, max_chars=2_000) or "subtitle generation failed"
        self.store.fail_job(job_id, error_text=error_tail, exit_code=exit_code)

    @staticmethod
    def _pump_output(pipe: Any, log_handle: Any) -> None:
        for line in iter(pipe.readline, ""):
            clean_line = ANSI_ESCAPE_RE.sub("", line)
            log_handle.write(clean_line)
            log_handle.flush()
        pipe.close()


class WebRuntime:
    """Application runtime shared across FastAPI handlers."""

    def __init__(self, settings: WebSettings) -> None:
        self.settings = settings
        self.store = JobStore(settings)
        self.worker = JobWorker(settings, self.store)

    def start(self) -> None:
        self.worker.start()

    def stop(self) -> None:
        self.worker.stop()


def save_upload_file(file_obj: Any, destination: Path, max_upload_bytes: int) -> int:
    """Persist an uploaded file while enforcing the size limit."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    bytes_written = 0
    with destination.open("wb") as handle:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            bytes_written += len(chunk)
            if bytes_written > max_upload_bytes:
                raise InvalidJobOptionsError("uploaded file exceeds the configured size limit")
            handle.write(chunk)
    return bytes_written
