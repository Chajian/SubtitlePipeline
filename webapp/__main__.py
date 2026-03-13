"""Module entrypoint for running the web shell."""

from __future__ import annotations

from pathlib import Path

from subtitle.env_loader import load_env_file
from webapp.service import WebSettings


def main() -> None:
    import uvicorn

    root_dir = Path(__file__).resolve().parent.parent
    load_env_file(root_dir / ".env.web.local", override=False)
    settings = WebSettings.from_env(root_dir)
    uvicorn.run("webapp.app:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
