from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path


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


def test_grant_token_cannot_access_private_exposure_release() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-access-grant-boundary-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory
        from server.models import AccessGrant
        from server.modules.access import service as access_service

        client = TestClient(create_app())
        owner_headers = {"Authorization": "Bearer fixture-maintainer-token"}

        release_id = create_ready_release(
            client,
            owner_headers,
            slug="grant-boundary-skill",
            display_name="Grant Boundary Skill",
        )
        exposure_response = client.post(
            f"/api/v1/releases/{release_id}/exposures",
            headers=owner_headers,
            json={
                "audience_type": "private",
                "listing_mode": "direct_only",
                "install_mode": "enabled",
                "requested_review_mode": "none",
            },
        )
        assert exposure_response.status_code == 201, exposure_response.text
        exposure_id = int(exposure_response.json()["id"])

        session_factory = get_session_factory()
        with session_factory() as session:
            grant = AccessGrant(
                exposure_id=exposure_id,
                grant_type="link",
                subject_ref="grant-boundary-fixture",
                constraints_json="{}",
                state="active",
                created_by_principal_id=None,
            )
            session.add(grant)
            session.flush()
            raw_token, _credential = access_service.create_grant_token(session, grant=grant)
            session.commit()

        response = client.get(
            f"/api/v1/access/releases/{release_id}/check",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "release access denied"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
