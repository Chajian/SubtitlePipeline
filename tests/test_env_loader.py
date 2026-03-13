from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from subtitle.env_loader import bootstrap_ai_review_env, load_env_file


class EnvLoaderTest(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        temp_root = Path.cwd() / ".tmp" / "tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_dir = temp_root / f"run-{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return temp_dir

    def test_load_env_file_reads_simple_assignments(self) -> None:
        temp_dir = self._make_temp_dir()
        env_path = temp_dir / ".env.ai-review.local"
        env_path.write_text(
            "# comment\n"
            "AI_REVIEW_MODE=on\n"
            "AI_REVIEW_MODEL='Pro/moonshotai/Kimi-K2.5'\n"
            "export SILICONFLOW_API_KEY=test-key\n",
            encoding="utf-8",
        )

        original = os.environ.copy()
        self.addCleanup(lambda: os.environ.clear() or os.environ.update(original))

        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            loaded = load_env_file(env_path)
            self.assertEqual(os.environ["AI_REVIEW_MODE"], "on")
            self.assertEqual(os.environ["AI_REVIEW_MODEL"], "Pro/moonshotai/Kimi-K2.5")
            self.assertEqual(os.environ["SILICONFLOW_API_KEY"], "test-key")
            self.assertEqual(
                loaded,
                ["AI_REVIEW_MODE", "AI_REVIEW_MODEL", "SILICONFLOW_API_KEY"],
            )

    def test_bootstrap_loads_common_then_provider_file(self) -> None:
        temp_dir = self._make_temp_dir()
        (temp_dir / ".env.ai-review.local").write_text(
            "AI_REVIEW_MODE=on\n"
            "AI_REVIEW_PROVIDER=siliconflow\n",
            encoding="utf-8",
        )
        (temp_dir / ".env.ai-review.siliconflow.local").write_text(
            "AI_REVIEW_MODEL=Pro/moonshotai/Kimi-K2.5\n"
            "SILICONFLOW_API_KEY=test-key\n",
            encoding="utf-8",
        )

        original = os.environ.copy()
        self.addCleanup(lambda: os.environ.clear() or os.environ.update(original))
        os.environ.pop("AI_REVIEW_MODE", None)
        os.environ.pop("AI_REVIEW_PROVIDER", None)
        os.environ.pop("AI_REVIEW_MODEL", None)
        os.environ.pop("SILICONFLOW_API_KEY", None)

        loaded_files = bootstrap_ai_review_env(temp_dir)

        self.assertEqual(
            loaded_files,
            [
                temp_dir / ".env.ai-review.local",
                temp_dir / ".env.ai-review.siliconflow.local",
            ],
        )
        self.assertEqual(os.environ["AI_REVIEW_PROVIDER"], "siliconflow")
        self.assertEqual(os.environ["AI_REVIEW_MODEL"], "Pro/moonshotai/Kimi-K2.5")
        self.assertEqual(os.environ["SILICONFLOW_API_KEY"], "test-key")

    def test_bootstrap_preserves_existing_shell_env(self) -> None:
        temp_dir = self._make_temp_dir()
        (temp_dir / ".env.ai-review.local").write_text(
            "AI_REVIEW_PROVIDER=siliconflow\n",
            encoding="utf-8",
        )
        (temp_dir / ".env.ai-review.openai.local").write_text(
            "AI_REVIEW_MODEL=gpt-4.1-mini\n"
            "OPENAI_API_KEY=openai-key\n",
            encoding="utf-8",
        )
        (temp_dir / ".env.ai-review.siliconflow.local").write_text(
            "AI_REVIEW_MODEL=Pro/moonshotai/Kimi-K2.5\n"
            "SILICONFLOW_API_KEY=silicon-key\n",
            encoding="utf-8",
        )

        original = os.environ.copy()
        self.addCleanup(lambda: os.environ.clear() or os.environ.update(original))
        os.environ["AI_REVIEW_PROVIDER"] = "openai"
        os.environ.pop("AI_REVIEW_MODEL", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("SILICONFLOW_API_KEY", None)

        loaded_files = bootstrap_ai_review_env(temp_dir)

        self.assertEqual(loaded_files, [temp_dir / ".env.ai-review.openai.local"])
        self.assertEqual(os.environ["AI_REVIEW_PROVIDER"], "openai")
        self.assertEqual(os.environ["AI_REVIEW_MODEL"], "gpt-4.1-mini")
        self.assertEqual(os.environ["OPENAI_API_KEY"], "openai-key")
        self.assertNotIn("SILICONFLOW_API_KEY", os.environ)


if __name__ == "__main__":
    unittest.main()
