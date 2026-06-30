#!/usr/bin/env python3
"""Generate a static openapi.json from the FastAPI application."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    # Use a temp file DB so migrations can run
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    os.environ.setdefault("INFINITAS_SERVER_SECRET_KEY", "generate-openapi-secret")
    os.environ.setdefault("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{db_path}")
    os.environ.setdefault("INFINITAS_SERVER_ARTIFACT_PATH", tempfile.mkdtemp())
    os.environ.setdefault("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
    os.environ.setdefault("INFINITAS_SERVER_ALLOWED_HOSTS", '["localhost"]')

    # Suppress alembic migration logs
    import logging

    logging.getLogger("alembic.runtime.migration").setLevel(logging.WARNING)

    from server.app import app

    openapi = app.openapi()
    out_path = Path(__file__).resolve().parents[1] / "openapi.json"
    out_path.write_text(json.dumps(openapi, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {out_path} with {len(openapi.get('paths', {}))} paths")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
