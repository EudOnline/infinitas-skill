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


def create_grant_token(session_factory, *, exposure_id: int, owner_slug: str) -> str:
    from server.models import AccessGrant, Principal
    from server.modules.access.service import create_grant_token

    with session_factory() as session:
        owner = session.scalar(
            select(Principal).where(Principal.kind == "user").where(Principal.slug == owner_slug)
        )
        if owner is None:
            fail(f"expected owner principal {owner_slug!r} to exist")

        grant = AccessGrant(
            exposure_id=exposure_id,
            grant_type="link",
            subject_ref=f"principal:{owner.id}",
            constraints_json="{}",
            state="active",
            created_by_principal_id=owner.id,
        )
        session.add(grant)
        session.flush()
        raw_token, _credential = create_grant_token(session, grant=grant, principal_id=None)
        session.commit()
        return raw_token


def scenario_grant_install_resolution_can_download_bound_artifacts() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-grant-install-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory

        client = TestClient(create_app())
        session_factory = get_session_factory()
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        granted_release_id = create_ready_release(
            client,
            headers,
            slug="grant-downloadable-skill",
            display_name="Grant Downloadable Skill",
        )
        blocked_release_id = create_ready_release(
            client,
            headers,
            slug="other-private-skill",
            display_name="Other Private Skill",
        )

        grant_exposure = create_exposure(
            client,
            headers,
            release_id=granted_release_id,
            audience_type="grant",
            listing_mode="listed",
            requested_review_mode="none",
        )
        create_exposure(
            client,
            headers,
            release_id=blocked_release_id,
            audience_type="private",
            listing_mode="direct_only",
            requested_review_mode="none",
        )
        grant_token = create_grant_token(
            session_factory,
            exposure_id=int(grant_exposure["id"]),
            owner_slug="fixture-maintainer",
        )
        grant_headers = {"Authorization": f"Bearer {grant_token}"}

        install_response = client.get(
            "/api/v1/install/grant/fixture-maintainer/grant-downloadable-skill",
            headers=grant_headers,
        )
        if install_response.status_code != 200:
            fail(
                "expected granted install resolution to return 200, "
                f"got {install_response.status_code}: {install_response.text}"
            )
        payload = install_response.json()
        for field in [
            "manifest_download_path",
            "bundle_download_path",
            "provenance_download_path",
            "signature_download_path",
        ]:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                fail(f"expected install payload field {field!r}, got {payload!r}")

        for field in [
            "manifest_download_path",
            "bundle_download_path",
            "provenance_download_path",
            "signature_download_path",
        ]:
            download_response = client.get(payload[field], headers=grant_headers)
            if download_response.status_code != 200:
                fail(
                    f"expected download from {field} to return 200, "
                    f"got {download_response.status_code}: {download_response.text}"
                )
            if not download_response.content:
                fail(f"expected {field} download to contain bytes")

        denied = client.get(
            "/api/v1/install/grant/fixture-maintainer/other-private-skill",
            headers=grant_headers,
        )
        if denied.status_code not in {403, 404}:
            fail(f"expected non-granted install resolution to be blocked, got {denied.status_code}: {denied.text}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_grant_install_resolution_can_download_bound_artifacts()
    print("OK: private registry grant install checks passed")


if __name__ == "__main__":
    main()
