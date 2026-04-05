#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(
        [
            {
                "username": "fixture-maintainer",
                "display_name": "Fixture Maintainer",
                "role": "maintainer",
                "token": "fixture-maintainer-token",
            }
        ]
    )
    os.environ.pop("INFINITAS_REGISTRY_READ_TOKENS", None)

    from server.db import get_engine, get_session_factory
    from server.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def scenario_public_search_does_not_fallback_to_repo_catalog() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-public-search-no-repo-catalog-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/api/search", params={"q": "operate", "scope": "public"})
        if response.status_code != 200:
            fail(f"expected public search 200, got {response.status_code}: {response.text}")

        payload = response.json()
        skills = payload.get("skills") or []
        if skills:
            fail(f"expected empty public search results without hosted snapshot, got {skills!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_does_not_render_repo_catalog_when_hosted_snapshot_is_missing() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-public-home-no-repo-catalog-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/?lang=en")
        if response.status_code != 200:
            fail(f"expected home page 200, got {response.status_code}: {response.text}")

        html = response.text
        leaked_markers = [
            "operate-infinitas-skill",
            "Teach OpenClaw, Codex, and Claude Code",
        ]
        present = [marker for marker in leaked_markers if marker in html]
        if present:
            fail(
                "expected anonymous home page to avoid repo-catalog featured skills when "
                f"hosted snapshot is missing, found {present}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_public_search_does_not_fallback_to_repo_catalog()
    scenario_home_does_not_render_repo_catalog_when_hosted_snapshot_is_missing()
    print("OK: public surface avoids repo catalog fallback checks passed")


if __name__ == "__main__":
    main()
