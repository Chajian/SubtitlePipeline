#!/usr/bin/env python3
"""Export subtitle AI review environment variables from local cc-switch config."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CC_SWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


@dataclass(slots=True)
class ProviderEnv:
    """Provider-specific environment variables for subtitle AI review."""

    provider: str
    model: str
    secret_env_name: str
    secret_value: str
    base_url: str | None = None
    source_label: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export subtitle AI review environment variables from cc-switch.",
    )
    parser.add_argument(
        "--provider",
        default="all",
        choices=["all", "openai", "siliconflow"],
        help="Provider to export (default: all)",
    )
    parser.add_argument(
        "--format",
        default="powershell",
        choices=["powershell", "cmd", "sh", "env"],
        help="Output format (default: powershell)",
    )
    parser.add_argument(
        "--cc-switch-db",
        default=str(DEFAULT_CC_SWITCH_DB),
        help="Path to cc-switch.db",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.cc_switch_db)
    if not db_path.exists():
        print(f"cc-switch db not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    try:
        providers: list[ProviderEnv] = []
        if args.provider in {"all", "openai"}:
            provider = extract_openai_provider(conn)
            if provider is None and args.provider == "openai":
                raise SystemExit("openai provider not found in cc-switch config")
            if provider is not None:
                providers.append(provider)

        if args.provider in {"all", "siliconflow"}:
            provider = extract_siliconflow_provider(conn)
            if provider is None and args.provider == "siliconflow":
                raise SystemExit("siliconflow provider not found in cc-switch config")
            if provider is not None:
                providers.append(provider)
    finally:
        conn.close()

    if not providers:
        print("no matching providers found", file=sys.stderr)
        sys.exit(1)

    for index, provider in enumerate(providers):
        if index:
            print()
        print(render_provider_block(provider, args.format))


def extract_openai_provider(conn: sqlite3.Connection) -> ProviderEnv | None:
    rows = conn.execute(
        """
        select app_type, name, is_current, category, settings_config
        from providers
        where settings_config like '%OPENAI_API_KEY%'
           or lower(name) like 'openai official%'
        order by
            case when app_type = 'codex' then 0 else 1 end,
            is_current desc,
            case when category = 'official' then 0 else 1 end,
            name asc
        """,
    ).fetchall()

    for app_type, name, is_current, category, settings_config in rows:
        config = load_json(settings_config)
        auth = config.get("auth")
        if not isinstance(auth, dict):
            continue
        api_key = auth.get("OPENAI_API_KEY")
        if not isinstance(api_key, str) or not api_key:
            continue
        source_label = f"{name} ({app_type}, current={bool(is_current)}, category={category or 'n/a'})"
        return ProviderEnv(
            provider="openai",
            model=DEFAULT_OPENAI_MODEL,
            secret_env_name="OPENAI_API_KEY",
            secret_value=api_key,
            source_label=source_label,
        )

    return None


def extract_siliconflow_provider(conn: sqlite3.Connection) -> ProviderEnv | None:
    rows = conn.execute(
        """
        select app_type, name, settings_config
        from providers
        where lower(name) like '%siliconflow%'
           or settings_config like '%api.siliconflow.cn%'
        order by
            case when lower(name) like '%siliconflow%' then 0 else 1 end,
            app_type asc,
            name asc
        """,
    ).fetchall()

    for app_type, name, settings_config in rows:
        config = load_json(settings_config)
        api_key = config.get("apiKey")
        if not isinstance(api_key, str) or not api_key:
            continue
        base_url = config.get("baseUrl")
        if not isinstance(base_url, str) or not base_url:
            base_url = "https://api.siliconflow.cn/v1"

        model = ""
        models = config.get("models")
        if isinstance(models, list):
            for item in models:
                if isinstance(item, dict):
                    model_id = item.get("id")
                    if isinstance(model_id, str) and model_id:
                        model = model_id
                        break
        if not model:
            model = "Pro/moonshotai/Kimi-K2.5"

        source_label = f"{name} ({app_type})"
        return ProviderEnv(
            provider="siliconflow",
            model=model,
            secret_env_name="SILICONFLOW_API_KEY",
            secret_value=api_key,
            base_url=base_url,
            source_label=source_label,
        )

    return None


def load_json(raw_text: str | None) -> dict[str, object]:
    if not raw_text:
        return {}
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def render_provider_block(provider: ProviderEnv, output_format: str) -> str:
    lines = [
        render_comment(
            f"subtitle-pipeline AI review env for {provider.provider}"
            + (f" | source: {provider.source_label}" if provider.source_label else ""),
            output_format,
        ),
    ]

    env_items: list[tuple[str, str]] = [
        ("AI_REVIEW_MODE", "on"),
        ("AI_REVIEW_PROVIDER", provider.provider),
        ("AI_REVIEW_MODEL", provider.model),
        (provider.secret_env_name, provider.secret_value),
    ]
    if provider.base_url:
        env_items.append(("AI_REVIEW_BASE_URL", provider.base_url))

    for name, value in env_items:
        lines.append(render_assignment(name, value, output_format))

    return "\n".join(lines)


def render_comment(text: str, output_format: str) -> str:
    if output_format in {"env", "sh"}:
        return f"# {text}"
    return f"REM {text}" if output_format == "cmd" else f"# {text}"


def render_assignment(name: str, value: str, output_format: str) -> str:
    escaped = value.replace("'", "''")
    if output_format == "powershell":
        return f"$env:{name} = '{escaped}'"
    if output_format == "cmd":
        return f"set {name}={value}"
    if output_format == "sh":
        sh_value = value.replace("'", "'\"'\"'")
        return f"export {name}='{sh_value}'"
    return f"{name}={value}"


if __name__ == "__main__":
    main()
