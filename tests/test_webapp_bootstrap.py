from __future__ import annotations

import unittest

from fastapi.testclient import TestClient


class WebAppBootstrapTest(unittest.TestCase):
    def test_web_app_boots_and_serves_basic_routes(self) -> None:
        from webapp.app import app

        with TestClient(app) as client:
            index_response = client.get("/")
            self.assertEqual(index_response.status_code, 200)
            self.assertIn("Subtitle Pipeline", index_response.text)

            health_response = client.get("/healthz")
            self.assertEqual(health_response.status_code, 200)
            self.assertEqual(health_response.json()["status"], "ok")

    def test_web_index_includes_history_panel_contract(self) -> None:
        from webapp.app import app

        with TestClient(app) as client:
            index_response = client.get("/")

        self.assertEqual(index_response.status_code, 200)
        self.assertIn("历史任务", index_response.text)
        self.assertIn('id="job-history"', index_response.text)
        self.assertIn("succeeded", index_response.text)

    def test_web_index_includes_public_status_cards_contract(self) -> None:
        from webapp.app import app

        with TestClient(app) as client:
            index_response = client.get("/")

        self.assertEqual(index_response.status_code, 200)
        self.assertIn('id="public-status-cards"', index_response.text)
        self.assertIn("今日剩余", index_response.text)
        self.assertIn("上传上限", index_response.text)

    def test_web_index_includes_submit_feedback_contract(self) -> None:
        from webapp.app import app

        with TestClient(app) as client:
            index_response = client.get("/")

        self.assertEqual(index_response.status_code, 200)
        self.assertIn('id="submit-status"', index_response.text)
        self.assertIn('id="submit-button"', index_response.text)
        self.assertIn("正在上传并提交任务", index_response.text)

    def test_web_index_mentions_draft_ready_and_review_failed_states(self) -> None:
        from webapp.app import app

        with TestClient(app) as client:
            index_response = client.get("/")

        self.assertEqual(index_response.status_code, 200)
        self.assertIn("初稿已生成，可下载", index_response.text)
        self.assertIn("AI 校对失败，初稿仍可下载", index_response.text)

    def test_web_index_includes_staged_status_helpers_contract(self) -> None:
        from webapp.app import app

        with TestClient(app) as client:
            index_response = client.get("/")

        self.assertEqual(index_response.status_code, 200)
        self.assertIn("function renderCompositeStatus(job)", index_response.text)
        self.assertIn("terminalPrimaryStatuses", index_response.text)
        self.assertIn("primary_status", index_response.text)
        self.assertIn("enhancement_status", index_response.text)
        self.assertIn("current_stage", index_response.text)


if __name__ == "__main__":
    unittest.main()
