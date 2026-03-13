from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from webapp.service import (
    InvalidJobOptionsError,
    JobStore,
    QuotaExceededError,
    QueueFullError,
    WebSettings,
    build_cli_command,
)


class WebServiceTest(unittest.TestCase):
    def _make_settings(self, *, daily_quota: int = 2, max_queue_size: int = 2) -> WebSettings:
        temp_root = Path.cwd() / ".tmp" / "tests" / f"web-{uuid4().hex}"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))
        return WebSettings(
            root_dir=Path.cwd(),
            data_dir=temp_root,
            db_path=temp_root / "app.db",
            uploads_dir=temp_root / "uploads",
            jobs_dir=temp_root / "jobs",
            timezone_name="Asia/Shanghai",
            daily_quota=daily_quota,
            max_upload_mb=50,
            max_queue_size=max_queue_size,
            job_timeout_seconds=300,
            result_ttl_hours=24,
            host="127.0.0.1",
            port=8000,
        )

    def test_build_cli_command_uses_web_form_options(self) -> None:
        settings = self._make_settings()
        command = build_cli_command(
            settings,
            settings.uploads_dir / "input.mp4",
            settings.jobs_dir / "job-1" / "output",
            {
                "model": "small",
                "zh_script": "traditional",
                "burn_subtitles": False,
                "ai_review": True,
            },
        )
        self.assertIn("--model", command)
        self.assertIn("small", command)
        self.assertIn("--zh-script", command)
        self.assertIn("traditional", command)
        self.assertIn("--ai-review", command)
        self.assertIn("on", command)
        self.assertIn("--no-burn", command)

    def test_invalid_model_is_rejected(self) -> None:
        settings = self._make_settings()
        with self.assertRaises(InvalidJobOptionsError):
            build_cli_command(
                settings,
                settings.uploads_dir / "input.mp4",
                settings.jobs_dir / "job-1" / "output",
                {
                    "model": "tiny",
                    "zh_script": "simplified",
                    "burn_subtitles": False,
                    "ai_review": False,
                },
            )

    def test_quota_is_global_and_exhausts_after_limit(self) -> None:
        settings = self._make_settings(daily_quota=1, max_queue_size=5)
        store = JobStore(settings)
        upload_path = settings.uploads_dir / "job-1.mp4"
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        upload_path.write_bytes(b"video")

        store.create_job(
            job_id="job-1",
            original_filename="job-1.mp4",
            upload_path=upload_path,
            output_dir=settings.jobs_dir / "job-1" / "output",
            log_path=settings.jobs_dir / "job-1" / "job.log",
            options={
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": False,
                "ai_review": False,
            },
        )

        with self.assertRaises(QuotaExceededError):
            store.create_job(
                job_id="job-2",
                original_filename="job-2.mp4",
                upload_path=settings.uploads_dir / "job-2.mp4",
                output_dir=settings.jobs_dir / "job-2" / "output",
                log_path=settings.jobs_dir / "job-2" / "job.log",
                options={
                    "model": "medium",
                    "zh_script": "simplified",
                    "burn_subtitles": False,
                    "ai_review": False,
                },
            )

    def test_queue_size_blocks_new_jobs(self) -> None:
        settings = self._make_settings(daily_quota=5, max_queue_size=1)
        store = JobStore(settings)
        upload_path = settings.uploads_dir / "job-1.mp4"
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        upload_path.write_bytes(b"video")

        store.create_job(
            job_id="job-1",
            original_filename="job-1.mp4",
            upload_path=upload_path,
            output_dir=settings.jobs_dir / "job-1" / "output",
            log_path=settings.jobs_dir / "job-1" / "job.log",
            options={
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": False,
                "ai_review": False,
            },
        )

        with self.assertRaises(QueueFullError):
            store.create_job(
                job_id="job-2",
                original_filename="job-2.mp4",
                upload_path=settings.uploads_dir / "job-2.mp4",
                output_dir=settings.jobs_dir / "job-2" / "output",
                log_path=settings.jobs_dir / "job-2" / "job.log",
                options={
                    "model": "medium",
                    "zh_script": "simplified",
                    "burn_subtitles": False,
                    "ai_review": False,
                },
            )
