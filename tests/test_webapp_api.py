from __future__ import annotations

import json
import shutil
import sqlite3
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from webapp.app import app
import webapp.service as service_module
from webapp.service import JobStore, WebSettings


class WebAppApiTest(unittest.TestCase):
    def _make_temp_root(self) -> Path:
        temp_root = Path.cwd() / ".tmp" / "tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_dir = temp_root / f"web-{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return temp_dir

    def _seed_jobs(self, settings: WebSettings) -> None:
        store = JobStore(settings)

        first_job_id = "job-old"
        first_output_dir = settings.jobs_dir / first_job_id / "output"
        first_output_dir.mkdir(parents=True, exist_ok=True)
        first_log_path = settings.jobs_dir / first_job_id / "job.log"
        first_log_path.write_text("old log", encoding="utf-8")
        store.create_job(
            job_id=first_job_id,
            original_filename="old.mp4",
            upload_path=settings.uploads_dir / f"{first_job_id}.mp4",
            output_dir=first_output_dir,
            log_path=first_log_path,
            options={
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": True,
                "ai_review": True,
            },
        )

        second_job_id = "job-new"
        second_output_dir = settings.jobs_dir / second_job_id / "output"
        second_output_dir.mkdir(parents=True, exist_ok=True)
        (second_output_dir / "job-new.cn.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
        second_log_path = settings.jobs_dir / second_job_id / "job.log"
        second_log_path.write_text("new log", encoding="utf-8")
        store.create_job(
            job_id=second_job_id,
            original_filename="new.mp4",
            upload_path=settings.uploads_dir / f"{second_job_id}.mp4",
            output_dir=second_output_dir,
            log_path=second_log_path,
            options={
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": True,
                "ai_review": True,
            },
        )
        store.complete_job(second_job_id, exit_code=0)

        conn = sqlite3.connect(settings.db_path)
        try:
            conn.execute(
                "UPDATE jobs SET created_at = ?, started_at = ?, completed_at = ? WHERE job_id = ?",
                ("2026-04-27T10:00:00+08:00", "2026-04-27T10:00:05+08:00", None, first_job_id),
            )
            conn.execute(
                "UPDATE jobs SET created_at = ?, started_at = ?, completed_at = ? WHERE job_id = ?",
                ("2026-04-27T11:00:00+08:00", "2026-04-27T11:00:05+08:00", "2026-04-27T11:10:00+08:00", second_job_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _add_staged_columns(self, settings: WebSettings) -> None:
        conn = sqlite3.connect(settings.db_path)
        try:
            existing = {
                row[1]
                for row in conn.execute("PRAGMA table_info(jobs)")
            }
            if "primary_status" not in existing:
                conn.execute("ALTER TABLE jobs ADD COLUMN primary_status TEXT")
            if "enhancement_status" not in existing:
                conn.execute("ALTER TABLE jobs ADD COLUMN enhancement_status TEXT")
            if "current_stage" not in existing:
                conn.execute("ALTER TABLE jobs ADD COLUMN current_stage TEXT")
            conn.commit()
        finally:
            conn.close()

    def _get_staged_row(self, settings: WebSettings, job_id: str) -> tuple[object, object, object] | None:
        conn = sqlite3.connect(settings.db_path)
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
        return row

    def _client_patches(self, settings: WebSettings) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch("webapp.app.WebSettings.from_env", return_value=settings))
        stack.enter_context(patch("webapp.app.WebRuntime.start", autospec=True))
        stack.enter_context(patch("webapp.app.WebRuntime.stop", autospec=True))
        return stack

    def test_list_jobs_returns_recent_jobs_descending(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        self._seed_jobs(settings)

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.get("/api/jobs")

        self.assertEqual(response.status_code, 200)
        jobs = response.json()
        self.assertEqual([job["job_id"] for job in jobs], ["job-new", "job-old"])
        self.assertEqual(jobs[0]["status"], "succeeded")
        self.assertEqual(jobs[0]["original_filename"], "new.mp4")
        self.assertEqual(jobs[0]["completed_at"], "2026-04-27T11:10:00+08:00")
        self.assertNotIn("files", jobs[0])

    def test_list_jobs_returns_primary_and_enhancement_status_fields(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        self._seed_jobs(settings)
        self._add_staged_columns(settings)

        conn = sqlite3.connect(settings.db_path)
        try:
            conn.execute(
                """
                UPDATE jobs
                SET primary_status = ?, enhancement_status = ?, current_stage = ?
                WHERE job_id = ?
                """,
                ("completed", "reviewing", "completed", "job-new"),
            )
            conn.execute(
                """
                UPDATE jobs
                SET primary_status = ?, enhancement_status = ?, current_stage = ?
                WHERE job_id = ?
                """,
                ("transcribing", "pending", "transcribing", "job-old"),
            )
            conn.commit()
        finally:
            conn.close()

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.get("/api/jobs")

        self.assertEqual(response.status_code, 200)
        jobs = response.json()
        self.assertEqual(jobs[0]["job_id"], "job-new")
        self.assertEqual(jobs[0]["primary_status"], "completed")
        self.assertEqual(jobs[0]["enhancement_status"], "succeeded")
        self.assertEqual(jobs[0]["current_stage"], "completed")
        self.assertEqual(jobs[1]["job_id"], "job-old")
        self.assertEqual(jobs[1]["primary_status"], "uploaded")
        self.assertEqual(jobs[1]["enhancement_status"], "pending")
        self.assertEqual(jobs[1]["current_stage"], "uploaded")

    def test_job_detail_exposes_files_for_succeeded_job(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        self._seed_jobs(settings)

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.get("/api/jobs/job-new")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "succeeded")
        self.assertTrue(payload["files"])
        self.assertEqual(payload["files"][0]["name"], "job-new.cn.srt")

    def test_job_detail_exposes_primary_and_enhancement_status(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        self._seed_jobs(settings)

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.get("/api/jobs/job-new")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["primary_status"], "completed")
        self.assertEqual(payload["enhancement_status"], "succeeded")
        self.assertEqual(payload["current_stage"], "completed")

    def test_job_detail_persists_staged_fields_for_completed_job(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        self._seed_jobs(settings)

        row = self._get_staged_row(settings, "job-new")

        self.assertEqual(row, ("completed", "succeeded", "completed"))

    def test_job_detail_normalizes_legacy_rows_with_null_staged_fields(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        self._seed_jobs(settings)
        self._add_staged_columns(settings)

        conn = sqlite3.connect(settings.db_path)
        try:
            conn.execute(
                """
                UPDATE jobs
                SET primary_status = NULL, enhancement_status = NULL, current_stage = NULL
                WHERE job_id = ?
                """,
                ("job-new",),
            )
            conn.commit()
        finally:
            conn.close()

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.get("/api/jobs/job-new")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["primary_status"], "completed")
        self.assertEqual(payload["enhancement_status"], "succeeded")
        self.assertEqual(payload["current_stage"], "completed")

    def test_job_detail_prefers_runtime_progress_state_over_legacy_running_status(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        store = JobStore(settings)

        job_id = "job-runtime-overlay"
        output_dir = settings.jobs_dir / job_id / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = settings.jobs_dir / job_id / "job.log"
        log_path.write_text("runtime overlay log", encoding="utf-8")
        store.create_job(
            job_id=job_id,
            original_filename="runtime.mp4",
            upload_path=settings.uploads_dir / f"{job_id}.mp4",
            output_dir=output_dir,
            log_path=log_path,
            options={
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": True,
                "ai_review": True,
            },
        )
        store.claim_next_job()
        (settings.jobs_dir / job_id / "job-state.json").write_text(
            json.dumps(
                {
                    "primary_status": "draft_ready",
                    "enhancement_status": "reviewing",
                    "current_stage": "reviewing",
                    "enhancement_error_text": None,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.get(f"/api/jobs/{job_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["primary_status"], "draft_ready")
        self.assertEqual(payload["enhancement_status"], "reviewing")
        self.assertEqual(payload["current_stage"], "reviewing")

    def test_create_job_accepts_mts_upload(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.post(
                    "/api/jobs",
                    files={"video": ("clip.MTS", b"fake mts payload", "video/MP2T")},
                )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["filename"], "clip.MTS")
        self.assertTrue((settings.uploads_dir / f'{payload["job_id"]}.mts').exists())

    def test_create_job_returns_staged_status_fields(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)

        with self._client_patches(settings):
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

    def test_create_job_persists_staged_fields(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.post(
                    "/api/jobs",
                    files={"video": ("clip.mp4", b"fake payload", "video/mp4")},
                )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        row = self._get_staged_row(settings, payload["job_id"])
        self.assertEqual(row, ("uploaded", "pending", "uploaded"))

    def test_create_job_succeeds_when_staged_persistence_fails(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        store = JobStore(settings)

        job_id = "job-create-stale"
        output_dir = settings.jobs_dir / job_id / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = settings.jobs_dir / job_id / "job.log"
        log_path.write_text("create stale log", encoding="utf-8")

        with patch("webapp.service._update_staged_columns", side_effect=sqlite3.OperationalError("simulated staged write failure")):
            store.create_job(
                job_id=job_id,
                original_filename="create-stale.mp4",
                upload_path=settings.uploads_dir / f"{job_id}.mp4",
                output_dir=output_dir,
                log_path=log_path,
                options={
                    "model": "medium",
                    "zh_script": "simplified",
                    "burn_subtitles": True,
                    "ai_review": True,
                },
            )

        loaded = store.get_job(job_id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["status"], "queued")
        self.assertEqual(loaded["primary_status"], "uploaded")
        self.assertEqual(loaded["enhancement_status"], "pending")
        self.assertEqual(loaded["current_stage"], "uploaded")

    def test_claim_next_job_updates_staged_fields_to_running(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        store = JobStore(settings)

        job_id = "job-claim"
        output_dir = settings.jobs_dir / job_id / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = settings.jobs_dir / job_id / "job.log"
        log_path.write_text("claim log", encoding="utf-8")
        store.create_job(
            job_id=job_id,
            original_filename="claim.mp4",
            upload_path=settings.uploads_dir / f"{job_id}.mp4",
            output_dir=output_dir,
            log_path=log_path,
            options={
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": True,
                "ai_review": True,
            },
        )

        claimed = store.claim_next_job()
        loaded = store.get_job(job_id)

        self.assertIsNotNone(claimed)
        self.assertIsNotNone(loaded)
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["primary_status"], "transcribing")
        self.assertEqual(claimed["enhancement_status"], "pending")
        self.assertEqual(claimed["current_stage"], "transcribing")
        self.assertEqual(loaded["status"], "running")
        self.assertEqual(loaded["primary_status"], "transcribing")
        self.assertEqual(loaded["enhancement_status"], "pending")
        self.assertEqual(loaded["current_stage"], "transcribing")
        self.assertEqual(
            self._get_staged_row(settings, job_id),
            ("transcribing", "pending", "transcribing"),
        )

    def test_get_job_normalizes_stale_staged_fields_after_claim_persistence_failure(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        store = JobStore(settings)

        job_id = "job-claim-stale"
        output_dir = settings.jobs_dir / job_id / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = settings.jobs_dir / job_id / "job.log"
        log_path.write_text("claim stale log", encoding="utf-8")
        store.create_job(
            job_id=job_id,
            original_filename="claim-stale.mp4",
            upload_path=settings.uploads_dir / f"{job_id}.mp4",
            output_dir=output_dir,
            log_path=log_path,
            options={
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": True,
                "ai_review": True,
            },
        )

        original_update = service_module._update_staged_columns

        def flaky_update(_store: JobStore, job_id_arg: str, values: dict[str, str]) -> None:
            if values["primary_status"] == "transcribing":
                raise sqlite3.OperationalError("simulated staged write failure")
            original_update(_store, job_id_arg, values)

        with patch("webapp.service._update_staged_columns", side_effect=flaky_update):
            with patch("webapp.service._persisted_staged_columns", side_effect=sqlite3.OperationalError("simulated staged read failure")):
                claimed = store.claim_next_job()

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["primary_status"], "transcribing")
        self.assertEqual(claimed["enhancement_status"], "pending")
        self.assertEqual(claimed["current_stage"], "transcribing")

        loaded = store.get_job(job_id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["status"], "running")
        self.assertEqual(loaded["primary_status"], "transcribing")
        self.assertEqual(loaded["enhancement_status"], "pending")
        self.assertEqual(loaded["current_stage"], "transcribing")
        self.assertEqual(
            self._get_staged_row(settings, job_id),
            ("transcribing", "pending", "transcribing"),
        )

    def test_fail_job_persists_failed_staged_fields(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        store = JobStore(settings)

        job_id = "job-fail"
        output_dir = settings.jobs_dir / job_id / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = settings.jobs_dir / job_id / "job.log"
        log_path.write_text("fail log", encoding="utf-8")
        store.create_job(
            job_id=job_id,
            original_filename="fail.mp4",
            upload_path=settings.uploads_dir / f"{job_id}.mp4",
            output_dir=output_dir,
            log_path=log_path,
            options={
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": True,
                "ai_review": True,
            },
        )

        store.fail_job(job_id, error_text="boom", exit_code=1)

        self.assertEqual(
            self._get_staged_row(settings, job_id),
            ("failed", "pending", "failed"),
        )

    def test_create_job_invalid_options_return_400(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.post(
                    "/api/jobs",
                    data={"model": "not-a-model"},
                    files={"video": ("clip.mp4", b"fake payload", "video/mp4")},
                )

        self.assertEqual(response.status_code, 400)

    def test_retry_enhancement_requeues_review_without_rerunning_primary(self) -> None:
        temp_root = self._make_temp_root()
        settings = WebSettings.from_env(temp_root)
        store = JobStore(settings)

        job_id = "job-review-failed"
        output_dir = settings.jobs_dir / job_id / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = settings.jobs_dir / job_id / "job.log"
        log_path.write_text("review failed log", encoding="utf-8")
        store.create_job(
            job_id=job_id,
            original_filename="review.mp4",
            upload_path=settings.uploads_dir / f"{job_id}.mp4",
            output_dir=output_dir,
            log_path=log_path,
            options={
                "model": "medium",
                "zh_script": "simplified",
                "burn_subtitles": True,
                "ai_review": True,
            },
        )
        store.complete_job(job_id, exit_code=0)
        (output_dir / f"{job_id}.cn.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n原文\n\n",
            encoding="utf-8",
        )
        (output_dir.parent / "job-state.json").write_text(
            json.dumps(
                {
                    "primary_status": "draft_ready",
                    "enhancement_status": "failed",
                    "current_stage": "draft_ready",
                    "enhancement_error_text": "expected 80 reviewed blocks, got 79",
                    "artifacts": [
                        {"name": f"{job_id}.cn.srt", "kind": "draft_subtitle", "status": "ready"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with self._client_patches(settings):
            with TestClient(app) as client:
                response = client.post(f"/api/jobs/{job_id}/retry-enhancement")

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["primary_status"], "draft_ready")
        self.assertEqual(payload["enhancement_status"], "pending")
        self.assertEqual(payload["current_stage"], "draft_ready")

        job = store.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["primary_status"], "draft_ready")
        self.assertEqual(job["enhancement_status"], "pending")
        self.assertEqual(job["current_stage"], "draft_ready")


if __name__ == "__main__":
    unittest.main()
