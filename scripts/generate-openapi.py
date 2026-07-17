#!/usr/bin/env python3
"""Generate or verify the static OpenAPI schema without starting the database."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the output schema is stale")
    parser.add_argument("--output", type=Path, default=ROOT / "openapi.json")
    return parser.parse_args()


def _configure_schema_environment() -> None:
    os.environ.update(
        INFINITAS_SERVER_ENV="test",
        INFINITAS_SERVER_SECRET_KEY="generate-openapi-secret",  # noqa: S106
        INFINITAS_SERVER_DATABASE_URL=f"sqlite:///{tempfile.gettempdir()}/openapi-unused.db",
        INFINITAS_SERVER_ARTIFACT_PATH=tempfile.gettempdir(),
        INFINITAS_SERVER_BOOTSTRAP_USERS="[]",
        INFINITAS_SERVER_ALLOWED_HOSTS='["localhost"]',
    )


def render_openapi() -> str:
    _configure_schema_environment()
    from server.settings import get_settings

    get_settings.cache_clear()

    from server.app import create_app

    payload = create_app().openapi()
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    args = parse_args()
    rendered = render_openapi()
    output_path = args.output.resolve()
    if args.check:
        current = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        if current != rendered:
            print(f"FAIL: OpenAPI schema is stale: {output_path}", file=sys.stderr)
            return 1
        print(f"OK: OpenAPI schema is current: {output_path}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    path_count = len(json.loads(rendered).get("paths", {}))
    print(f"Generated {output_path} with {path_count} paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
