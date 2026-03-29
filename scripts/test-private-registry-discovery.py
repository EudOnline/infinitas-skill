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
                "username": "fixture-outsider",
                "display_name": "Fixture Outsider",
                "role": "contributor",
                "token": "fixture-outsider-token",
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
        json={"decision": "approve", "note": "approved for discovery fixtures"},
    )
    if decision_response.status_code != 201:
        fail(
            "expected review approval to return 201, "
            f"got {decision_response.status_code}: {decision_response.text}"
        )


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


def list_names(payload: dict) -> list[str]:
    return sorted(item.get("name") for item in (payload.get("items") or []) if isinstance(item, dict))


def scenario_discovery_views_are_audience_aware() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-discovery-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory

        client = TestClient(create_app())
        session_factory = get_session_factory()
        owner_headers = {"Authorization": "Bearer fixture-maintainer-token"}

        public_release_id = create_ready_release(
            client,
            owner_headers,
            slug="reviewed-public-skill",
            display_name="Reviewed Public Skill",
        )
        private_release_id = create_ready_release(
            client,
            owner_headers,
            slug="private-owner-skill",
            display_name="Private Owner Skill",
        )
        grant_release_id = create_ready_release(
            client,
            owner_headers,
            slug="grant-shared-skill",
            display_name="Grant Shared Skill",
        )
        pending_public_release_id = create_ready_release(
            client,
            owner_headers,
            slug="pending-public-skill",
            display_name="Pending Public Skill",
        )

        public_exposure = create_exposure(
            client,
            owner_headers,
            release_id=public_release_id,
            audience_type="public",
            listing_mode="listed",
            requested_review_mode="none",
        )
        approve_exposure_review(client, session_factory, owner_headers, int(public_exposure["id"]))

        create_exposure(
            client,
            owner_headers,
            release_id=private_release_id,
            audience_type="private",
            listing_mode="direct_only",
            requested_review_mode="none",
        )

        grant_exposure = create_exposure(
            client,
            owner_headers,
            release_id=grant_release_id,
            audience_type="grant",
            listing_mode="listed",
            requested_review_mode="none",
        )
        grant_token = create_grant_token(
            session_factory,
            exposure_id=int(grant_exposure["id"]),
            owner_slug="fixture-maintainer",
        )

        create_exposure(
            client,
            owner_headers,
            release_id=pending_public_release_id,
            audience_type="public",
            listing_mode="listed",
            requested_review_mode="none",
        )

        public_response = client.get("/api/v1/search/public", params={"q": "skill"})
        if public_response.status_code != 200:
            fail(
                "expected public discovery search to return 200, "
                f"got {public_response.status_code}: {public_response.text}"
            )
        public_only_names = list_names(public_response.json())
        if public_only_names != ["reviewed-public-skill"]:
            fail(f"expected only reviewed public skill in anonymous search, got {public_only_names!r}")

        me_response = client.get(
            "/api/v1/search/me",
            params={"q": "skill"},
            headers=owner_headers,
        )
        if me_response.status_code != 200:
            fail(f"expected me search to return 200, got {me_response.status_code}: {me_response.text}")
        me_names = list_names(me_response.json())
        for required_name in ["grant-shared-skill", "private-owner-skill", "reviewed-public-skill"]:
            if required_name not in me_names:
                fail(f"expected {required_name!r} in me search results, got {me_names!r}")
        if "pending-public-skill" in me_names:
            fail(f"expected review_open public exposure to stay hidden, got {me_names!r}")

        grant_response = client.get(
            "/api/v1/catalog/grant",
            headers={"Authorization": f"Bearer {grant_token}"},
        )
        if grant_response.status_code != 200:
            fail(
                "expected grant catalog view to return 200, "
                f"got {grant_response.status_code}: {grant_response.text}"
            )
        grant_names = list_names(grant_response.json())
        if grant_names != ["grant-shared-skill"]:
            fail(f"expected only grant-shared-skill in grant catalog, got {grant_names!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_discovery_views_are_audience_aware()
    print("OK: private registry discovery checks passed")


if __name__ == "__main__":
    main()
