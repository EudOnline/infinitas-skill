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
                "username": "skill-owner",
                "display_name": "Skill Owner",
                "role": "contributor",
                "token": "skill-owner-token",
            },
        ]
    )


def test_maintainer_can_administer_contributor_owned_lifecycle_resources() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-maintainer-cross-namespace-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory
        from server.models import ReviewCase
        from server.worker import run_worker_loop

        client = TestClient(create_app())
        owner_headers = {"Authorization": "Bearer skill-owner-token"}
        maintainer_headers = {"Authorization": "Bearer fixture-maintainer-token"}

        create_skill = client.post(
            "/api/v1/skills",
            headers=owner_headers,
            json={
                "slug": "cross-namespace-skill",
                "display_name": "Cross Namespace Skill",
                "summary": "cross namespace maintainer fixture",
            },
        )
        assert create_skill.status_code == 201, create_skill.text
        skill_id = int(create_skill.json()["id"])

        create_draft = client.post(
            f"/api/v1/skills/{skill_id}/drafts",
            headers=owner_headers,
            json={
                "content_ref": "git+https://example.com/cross-namespace-skill.git#0123456789abcdef0123456789abcdef01234567",
                "metadata": {"entrypoint": "SKILL.md"},
            },
        )
        assert create_draft.status_code == 201, create_draft.text
        draft_id = int(create_draft.json()["id"])

        patch_draft = client.patch(
            f"/api/v1/drafts/{draft_id}",
            headers=maintainer_headers,
            json={"metadata": {"entrypoint": "SKILL.md", "maintained_by": "fixture-maintainer"}},
        )
        assert patch_draft.status_code == 200, patch_draft.text

        seal = client.post(
            f"/api/v1/drafts/{draft_id}/seal",
            headers=maintainer_headers,
            json={"version": "0.1.0"},
        )
        assert seal.status_code == 201, seal.text
        version_id = int((seal.json().get("skill_version") or {})["id"])

        release = client.post(
            f"/api/v1/versions/{version_id}/releases",
            headers=maintainer_headers,
        )
        assert release.status_code == 201, release.text
        release_id = int(release.json()["id"])

        processed = run_worker_loop(limit=1)
        assert processed == 1

        get_release = client.get(
            f"/api/v1/releases/{release_id}",
            headers=maintainer_headers,
        )
        assert get_release.status_code == 200, get_release.text

        create_exposure = client.post(
            f"/api/v1/releases/{release_id}/exposures",
            headers=maintainer_headers,
            json={
                "audience_type": "public",
                "listing_mode": "listed",
                "install_mode": "enabled",
                "requested_review_mode": "none",
            },
        )
        assert create_exposure.status_code == 201, create_exposure.text
        exposure_id = int(create_exposure.json()["id"])

        session_factory = get_session_factory()
        with session_factory() as session:
            review_case = session.scalar(
                select(ReviewCase).where(ReviewCase.exposure_id == exposure_id)
            )
            assert review_case is not None, f"expected review case for exposure {exposure_id}"
            review_case_id = int(review_case.id)

        get_review_case = client.get(
            f"/api/v1/review-cases/{review_case_id}",
            headers=maintainer_headers,
        )
        assert get_review_case.status_code == 200, get_review_case.text

        decision = client.post(
            f"/api/v1/review-cases/{review_case_id}/decisions",
            headers=maintainer_headers,
            json={"decision": "approve", "note": "approved by maintainer"},
        )
        assert decision.status_code == 201, decision.text
        assert decision.json()["state"] == "approved"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
