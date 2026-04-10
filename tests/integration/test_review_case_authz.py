from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import select


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
            },
            {
                "username": "outside-reviewer",
                "display_name": "Outside Reviewer",
                "role": "contributor",
                "token": "outside-reviewer-token",
            },
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
    assert create_skill_response.status_code == 201, create_skill_response.text
    skill_id = int(create_skill_response.json()["id"])

    create_draft_response = client.post(
        f"/api/v1/skills/{skill_id}/drafts",
        headers=headers,
        json={
            "content_ref": f"git+https://example.com/{slug}.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {"entrypoint": "SKILL.md"},
        },
    )
    assert create_draft_response.status_code == 201, create_draft_response.text
    draft_id = int(create_draft_response.json()["id"])

    seal_response = client.post(
        f"/api/v1/drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "0.1.0"},
    )
    assert seal_response.status_code == 201, seal_response.text
    version_id = int((seal_response.json().get("skill_version") or {})["id"])

    create_release_response = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers=headers,
    )
    assert create_release_response.status_code == 201, create_release_response.text
    release_id = int(create_release_response.json()["id"])

    processed = run_worker_loop(limit=1)
    assert processed == 1, f"expected worker to process 1 release job, got {processed}"
    return release_id


def test_review_case_api_requires_release_ownership() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-review-authz-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory
        from server.models import ReviewCase

        client = TestClient(create_app())
        owner_headers = {"Authorization": "Bearer fixture-maintainer-token"}
        outsider_headers = {"Authorization": "Bearer outside-reviewer-token"}

        release_id = create_ready_release(
            client,
            owner_headers,
            slug="review-authz-skill",
            display_name="Review Authz Skill",
        )
        exposure_response = client.post(
            f"/api/v1/releases/{release_id}/exposures",
            headers=owner_headers,
            json={
                "audience_type": "public",
                "listing_mode": "listed",
                "install_mode": "enabled",
                "requested_review_mode": "blocking",
            },
        )
        assert exposure_response.status_code == 201, exposure_response.text
        exposure_id = int(exposure_response.json()["id"])

        session_factory = get_session_factory()
        with session_factory() as session:
            review_case = session.scalar(
                select(ReviewCase).where(ReviewCase.exposure_id == exposure_id)
            )
            assert review_case is not None, f"expected review case for exposure {exposure_id}"
            review_case_id = int(review_case.id)

        get_response = client.get(
            f"/api/v1/review-cases/{review_case_id}",
            headers=outsider_headers,
        )
        assert get_response.status_code == 403, get_response.text
        assert get_response.json()["detail"] == "release namespace access denied"

        decision_response = client.post(
            f"/api/v1/review-cases/{review_case_id}/decisions",
            headers=outsider_headers,
            json={"decision": "approve", "note": "not allowed"},
        )
        assert decision_response.status_code == 403, decision_response.text
        assert decision_response.json()["detail"] == "release namespace access denied"

        owner_response = client.get(
            f"/api/v1/review-cases/{review_case_id}",
            headers=owner_headers,
        )
        assert owner_response.status_code == 200, owner_response.text
        assert owner_response.json()["id"] == review_case_id
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_create_review_case_rejects_unknown_mode() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-review-mode-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        owner_headers = {"Authorization": "Bearer fixture-maintainer-token"}

        release_id = create_ready_release(
            client,
            owner_headers,
            slug="review-mode-skill",
            display_name="Review Mode Skill",
        )
        exposure_response = client.post(
            f"/api/v1/releases/{release_id}/exposures",
            headers=owner_headers,
            json={
                "audience_type": "grant",
                "listing_mode": "listed",
                "install_mode": "enabled",
                "requested_review_mode": "none",
            },
        )
        assert exposure_response.status_code == 201, exposure_response.text
        exposure_id = int(exposure_response.json()["id"])

        response = client.post(
            f"/api/v1/exposures/{exposure_id}/review-cases",
            headers=owner_headers,
            json={"mode": "mystery"},
        )
        assert response.status_code == 422, response.text
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
