from __future__ import annotations

import sqlite3
import unittest

from scripts.export_ai_review_env import (
    extract_openai_provider,
    extract_siliconflow_provider,
    render_provider_block,
)


class ExportAIReviewEnvTest(unittest.TestCase):
    def _make_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            create table providers (
                id text primary key,
                app_type text not null,
                name text not null,
                settings_config text not null,
                category text,
                is_current integer not null default 0
            )
            """,
        )
        return conn

    def test_extract_openai_provider_prefers_codex_current(self) -> None:
        conn = self._make_conn()
        conn.execute(
            """
            insert into providers (id, app_type, name, settings_config, category, is_current)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                "provider-openai",
                "codex",
                "OpenAI Official",
                '{"auth":{"OPENAI_API_KEY":"sk-test"}}',
                "official",
                1,
            ),
        )

        provider = extract_openai_provider(conn)

        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider.provider, "openai")
        self.assertEqual(provider.secret_env_name, "OPENAI_API_KEY")
        self.assertEqual(provider.secret_value, "sk-test")
        self.assertEqual(provider.model, "gpt-4.1-mini")

    def test_extract_siliconflow_provider_reads_model_and_base_url(self) -> None:
        conn = self._make_conn()
        conn.execute(
            """
            insert into providers (id, app_type, name, settings_config, category, is_current)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                "provider-sf",
                "openclaw",
                "siliconflow / Pro/moonshotai/Kimi-K2.5",
                (
                    '{"apiKey":"sf-key","baseUrl":"https://api.siliconflow.cn/v1",'
                    '"models":[{"id":"Pro/moonshotai/Kimi-K2.5"}]}'
                ),
                None,
                0,
            ),
        )

        provider = extract_siliconflow_provider(conn)

        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider.provider, "siliconflow")
        self.assertEqual(provider.secret_env_name, "SILICONFLOW_API_KEY")
        self.assertEqual(provider.secret_value, "sf-key")
        self.assertEqual(provider.base_url, "https://api.siliconflow.cn/v1")
        self.assertEqual(provider.model, "Pro/moonshotai/Kimi-K2.5")

    def test_render_provider_block_outputs_powershell_assignments(self) -> None:
        conn = self._make_conn()
        conn.execute(
            """
            insert into providers (id, app_type, name, settings_config, category, is_current)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                "provider-openai",
                "codex",
                "OpenAI Official",
                '{"auth":{"OPENAI_API_KEY":"sk-test"}}',
                "official",
                1,
            ),
        )
        provider = extract_openai_provider(conn)
        assert provider is not None

        block = render_provider_block(provider, "powershell")

        self.assertIn("$env:AI_REVIEW_MODE = 'on'", block)
        self.assertIn("$env:AI_REVIEW_PROVIDER = 'openai'", block)
        self.assertIn("$env:AI_REVIEW_MODEL = 'gpt-4.1-mini'", block)
        self.assertIn("$env:OPENAI_API_KEY = 'sk-test'", block)


if __name__ == "__main__":
    unittest.main()
