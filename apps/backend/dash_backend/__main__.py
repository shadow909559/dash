"""Entry point for `python -m dash_backend` (used by the Windows scheduled task).

Optional overrides:
    python -m dash_backend --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="dash_backend", description="Run the DASH AI OS backend")
    parser.add_argument("--host", default=None, help="Bind address (default: settings/DASH_HOST, loopback)")
    parser.add_argument("--port", type=int, default=None, help="Port (default: settings/DASH_PORT)")
    args = parser.parse_args()

    import uvicorn

    from dash_backend.config import get_settings
    from dash_backend.main import app

    settings = get_settings()
    uvicorn.run(
        app,
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
