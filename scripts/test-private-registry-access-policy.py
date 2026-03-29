#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir / "artifacts")
    os.environ["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps(["legacy-reader-token"])
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
        json={"decision": "approve", "note": "approved for registry policy fixture"},
    )
    if decision_response.status_code != 201:
        fail(
            "expected review approval to return 201, "
            f"got {decision_response.status_code}: {decision_response.text}"
        )


def scenario_registry_access_uses_private_first_credentials() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-registry-policy-"))
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
            slug="policy-public-skill",
            display_name="Policy Public Skill",
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

        unauthorized = client.get(
            "/registry/ai-index.json",
            headers={"Authorization": "Bearer definitely-invalid-token"},
        )
        if unauthorized.status_code != 401:
            fail(f"expected invalid registry token to return 401, got {unauthorized.status_code}: {unauthorized.text}")

        anonymous = client.get("/registry/ai-index.json")
        if anonymous.status_code != 200:
            fail(f"expected anonymous registry ai-index to return 200, got {anonymous.status_code}: {anonymous.text}")
        anonymous_names = [
            item.get("qualified_name")
            for item in (anonymous.json().get("skills") or [])
            if isinstance(item, dict)
        ]
        if anonymous_names != ["fixture-maintainer/policy-public-skill"]:
            fail(f"expected anonymous ai-index to contain only public release, got {anonymous_names!r}")

        authorized = client.get("/registry/ai-index.json", headers=headers)
        if authorized.status_code != 200:
            fail(f"expected user token ai-index to return 200, got {authorized.status_code}: {authorized.text}")
        authorized_names = [
            item.get("qualified_name")
            for item in (authorized.json().get("skills") or [])
            if isinstance(item, dict)
        ]
        if authorized_names != ["fixture-maintainer/policy-public-skill"]:
            fail(f"expected user ai-index to remain private-first scoped, got {authorized_names!r}")

        me_response = client.get("/api/v1/me", headers=headers)
        if me_response.status_code != 200:
            fail(f"expected /api/v1/me to return 200, got {me_response.status_code}: {me_response.text}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_registry_access_uses_private_first_credentials()
    print("OK: private registry access policy checks passed")


if __name__ == "__main__":
    main()
