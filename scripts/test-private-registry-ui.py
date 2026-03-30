#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import ast
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
APP_PATH = ROOT / "server" / "app.py"
APP_LINE_BUDGET = 220


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def assert_ui_route_registration_boundary() -> None:
    module = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    imported = False
    delegated = False
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module == "server.ui.routes":
            if any(alias.name == "register_ui_routes" for alias in node.names):
                imported = True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "register_ui_routes":
            delegated = True
    if not imported or not delegated:
        fail("expected server.app to import and call register_ui_routes from server.ui.routes")


def assert_app_size_budget() -> None:
    line_count = len(APP_PATH.read_text(encoding="utf-8").splitlines())
    if line_count > APP_LINE_BUDGET:
        fail(
            f"expected server/app.py to stay within {APP_LINE_BUDGET} lines after UI extraction, "
            f"got {line_count}"
        )


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir / "artifacts")
    os.environ["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps(["registry-reader-token"])
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


def create_ready_release(client, headers: dict[str, str], *, slug: str, display_name: str) -> int:
    from server.worker import run_worker_loop

    create_skill_response = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": slug,
            "display_name": display_name,
            "summary": f"{display_name} summary",
        },
    )
    if create_skill_response.status_code != 201:
        fail(
            "expected skill creation to return 201, "
            f"got {create_skill_response.status_code}: {create_skill_response.text}"
        )
    skill_id = int(create_skill_response.json()["id"])

    create_draft_response = client.post(
        f"/api/v1/skills/{skill_id}/drafts",
        headers=headers,
        json={
            "content_ref": f"git+https://example.com/{slug}.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {
                "entrypoint": "SKILL.md",
                "language": "zh-CN",
                "manifest": {"name": slug, "version": "0.1.0"},
            },
        },
    )
    if create_draft_response.status_code != 201:
        fail(
            "expected draft creation to return 201, "
            f"got {create_draft_response.status_code}: {create_draft_response.text}"
        )
    draft_id = int(create_draft_response.json()["id"])

    seal_response = client.post(
        f"/api/v1/drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "0.1.0"},
    )
    if seal_response.status_code != 201:
        fail(f"expected seal to return 201, got {seal_response.status_code}: {seal_response.text}")
    version_id = int((seal_response.json().get("skill_version") or {})["id"])

    create_release_response = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers=headers,
    )
    if create_release_response.status_code != 201:
        fail(
            "expected release creation to return 201, "
            f"got {create_release_response.status_code}: {create_release_response.text}"
        )
    release_id = int(create_release_response.json()["id"])
    processed = run_worker_loop(limit=1)
    if processed != 1:
        fail(f"expected worker to process 1 release job, got {processed}")
    return release_id


def create_exposure(
    client,
    headers: dict[str, str],
    *,
    release_id: int,
    audience_type: str,
    listing_mode: str,
    requested_review_mode: str,
) -> dict:
    response = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers=headers,
        json={
            "audience_type": audience_type,
            "listing_mode": listing_mode,
            "install_mode": "enabled",
            "requested_review_mode": requested_review_mode,
        },
    )
    if response.status_code != 201:
        fail(
            "expected exposure creation to return 201, "
            f"got {response.status_code}: {response.text}"
        )
    return response.json()


def approve_exposure_review(client, session_factory, headers: dict[str, str], exposure_id: int) -> None:
    from server.models import ReviewCase

    with session_factory() as session:
        review_case = session.scalar(select(ReviewCase).where(ReviewCase.exposure_id == exposure_id))
        if review_case is None:
            fail(f"expected review case for exposure {exposure_id}")
        review_case_id = review_case.id

    decision_response = client.post(
        f"/api/v1/review-cases/{review_case_id}/decisions",
        headers=headers,
        json={"decision": "approve", "note": "approved for ui fixture"},
    )
    if decision_response.status_code != 201:
        fail(
            "expected review approval to return 201, "
            f"got {decision_response.status_code}: {decision_response.text}"
        )


def scenario_private_first_console_ui() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-ui-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory

        client = TestClient(create_app())
        session_factory = get_session_factory()
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        release_id = create_ready_release(
            client,
            headers,
            slug="console-ui-skill",
            display_name="Console UI Skill",
        )

        create_exposure(
            client,
            headers,
            release_id=release_id,
            audience_type="private",
            listing_mode="direct_only",
            requested_review_mode="none",
        )

        create_exposure(
            client,
            headers,
            release_id=release_id,
            audience_type="grant",
            listing_mode="listed",
            requested_review_mode="none",
        )

        public_exposure = create_exposure(
            client,
            headers,
            release_id=release_id,
            audience_type="public",
            listing_mode="listed",
            requested_review_mode="none",
        )
        approve_exposure_review(client, session_factory, headers, int(public_exposure["id"]))

        home_html = client.get("/").text
        if "私人技能库" not in home_html:
            fail("expected homepage copy to describe a private-first skill library")
        for marker in ["id=\"user-panel-login\"", "id=\"open-auth-modal-btn\""]:
            if marker not in home_html:
                fail(f"expected homepage auth panel marker {marker!r} in homepage html")

        skills_response = client.get("/skills?lang=en", headers=headers)
        if skills_response.status_code != 200:
            fail(f"expected skills page to return 200, got {skills_response.status_code}: {skills_response.text}")
        skills_html = skills_response.text
        for label in ["Skills", "Drafts", "Releases", "Share", "Access", "Review"]:
            if label not in skills_html:
                fail(f"expected console navigation label {label!r} in skills page")

        share_response = client.get(f"/releases/{release_id}/share?lang=en", headers=headers)
        if share_response.status_code != 200:
            fail(f"expected share detail page to return 200, got {share_response.status_code}: {share_response.text}")
        share_html = share_response.text
        for label in ["Private", "Shared by token", "Public"]:
            if label not in share_html:
                fail(f"expected share detail page to include audience label {label!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    assert_ui_route_registration_boundary()
    assert_app_size_budget()
    scenario_private_first_console_ui()
    print("OK: private registry ui checks passed")


if __name__ == "__main__":
    main()
