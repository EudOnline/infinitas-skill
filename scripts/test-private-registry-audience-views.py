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
            "content_ref": f"git+https://example.com/{slug}.git#fedcba9876543210fedcba9876543210fedcba98",
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
        json={"decision": "approve", "note": "approved for registry audience fixture"},
    )
    if decision_response.status_code != 201:
        fail(
            "expected review approval to return 201, "
            f"got {decision_response.status_code}: {decision_response.text}"
        )


def create_bound_grant_token(session_factory, *, exposure_id: int, owner_slug: str) -> str:
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


def scenario_registry_surfaces_are_audience_scoped() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-registry-audience-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory

        client = TestClient(create_app())
        session_factory = get_session_factory()
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        public_release_id = create_ready_release(
            client,
            headers,
            slug="public-listed-skill",
            display_name="Public Listed Skill",
        )
        private_release_id = create_ready_release(
            client,
            headers,
            slug="private-direct-skill",
            display_name="Private Direct Skill",
        )
        grant_release_id = create_ready_release(
            client,
            headers,
            slug="grant-listed-skill",
            display_name="Grant Listed Skill",
        )
        pending_release_id = create_ready_release(
            client,
            headers,
            slug="pending-public-skill",
            display_name="Pending Public Skill",
        )

        public_exposure = create_exposure(
            client,
            headers,
            release_id=public_release_id,
            audience_type="public",
            listing_mode="listed",
            requested_review_mode="none",
        )
        approve_exposure_review(client, session_factory, headers, int(public_exposure["id"]))

        create_exposure(
            client,
            headers,
            release_id=private_release_id,
            audience_type="private",
            listing_mode="direct_only",
            requested_review_mode="none",
        )

        grant_exposure = create_exposure(
            client,
            headers,
            release_id=grant_release_id,
            audience_type="grant",
            listing_mode="listed",
            requested_review_mode="none",
        )
        grant_token = create_bound_grant_token(
            session_factory,
            exposure_id=int(grant_exposure["id"]),
            owner_slug="fixture-maintainer",
        )

        create_exposure(
            client,
            headers,
            release_id=pending_release_id,
            audience_type="public",
            listing_mode="listed",
            requested_review_mode="none",
        )

        anonymous_ai = client.get("/registry/ai-index.json")
        if anonymous_ai.status_code != 200:
            fail(f"expected anonymous ai-index to return 200, got {anonymous_ai.status_code}: {anonymous_ai.text}")
        anonymous_ai_names = [
            item.get("qualified_name")
            for item in (anonymous_ai.json().get("skills") or [])
            if isinstance(item, dict)
        ]
        if anonymous_ai_names != ["fixture-maintainer/public-listed-skill"]:
            fail(f"expected anonymous ai-index to include only approved public release, got {anonymous_ai_names!r}")

        anonymous_discovery = client.get("/registry/discovery-index.json")
        if anonymous_discovery.status_code != 200:
            fail(
                "expected anonymous discovery-index to return 200, "
                f"got {anonymous_discovery.status_code}: {anonymous_discovery.text}"
            )
        anonymous_discovery_names = [
            item.get("qualified_name")
            for item in (anonymous_discovery.json().get("skills") or [])
            if isinstance(item, dict)
        ]
        if anonymous_discovery_names != ["fixture-maintainer/public-listed-skill"]:
            fail(f"expected anonymous discovery-index to include only listed public release, got {anonymous_discovery_names!r}")

        maintainer_ai = client.get("/registry/ai-index.json", headers=headers)
        if maintainer_ai.status_code != 200:
            fail(f"expected maintainer ai-index to return 200, got {maintainer_ai.status_code}: {maintainer_ai.text}")
        maintainer_ai_names = sorted(
            item.get("qualified_name")
            for item in (maintainer_ai.json().get("skills") or [])
            if isinstance(item, dict)
        )
        expected_maintainer_ai = sorted(
            [
                "fixture-maintainer/public-listed-skill",
                "fixture-maintainer/private-direct-skill",
                "fixture-maintainer/grant-listed-skill",
            ]
        )
        if maintainer_ai_names != expected_maintainer_ai:
            fail(f"expected maintainer ai-index to include accessible releases, got {maintainer_ai_names!r}")

        maintainer_discovery = client.get("/registry/discovery-index.json", headers=headers)
        if maintainer_discovery.status_code != 200:
            fail(
                "expected maintainer discovery-index to return 200, "
                f"got {maintainer_discovery.status_code}: {maintainer_discovery.text}"
            )
        maintainer_discovery_names = sorted(
            item.get("qualified_name")
            for item in (maintainer_discovery.json().get("skills") or [])
            if isinstance(item, dict)
        )
        expected_maintainer_discovery = sorted(
            [
                "fixture-maintainer/public-listed-skill",
                "fixture-maintainer/grant-listed-skill",
            ]
        )
        if maintainer_discovery_names != expected_maintainer_discovery:
            fail(
                "expected maintainer discovery-index to hide direct-only releases while keeping listed grant/public entries, "
                f"got {maintainer_discovery_names!r}"
            )

        grant_headers = {"Authorization": f"Bearer {grant_token}"}
        grant_ai = client.get("/registry/ai-index.json", headers=grant_headers)
        if grant_ai.status_code != 200:
            fail(f"expected grant ai-index to return 200, got {grant_ai.status_code}: {grant_ai.text}")
        grant_ai_names = [
            item.get("qualified_name")
            for item in (grant_ai.json().get("skills") or [])
            if isinstance(item, dict)
        ]
        if grant_ai_names != ["fixture-maintainer/grant-listed-skill"]:
            fail(f"expected grant ai-index to contain only the granted release, got {grant_ai_names!r}")

        grant_discovery = client.get("/registry/discovery-index.json", headers=grant_headers)
        if grant_discovery.status_code != 200:
            fail(
                "expected grant discovery-index to return 200, "
                f"got {grant_discovery.status_code}: {grant_discovery.text}"
            )
        grant_discovery_names = [
            item.get("qualified_name")
            for item in (grant_discovery.json().get("skills") or [])
            if isinstance(item, dict)
        ]
        if grant_discovery_names != ["fixture-maintainer/grant-listed-skill"]:
            fail(f"expected grant discovery-index to contain only the granted listed release, got {grant_discovery_names!r}")

        public_manifest = client.get("/registry/catalog/distributions/fixture-maintainer/public-listed-skill/0.1.0/manifest.json")
        if public_manifest.status_code != 200:
            fail(
                "expected anonymous catalog alias manifest access to succeed for public release, "
                f"got {public_manifest.status_code}: {public_manifest.text}"
            )

        private_manifest = client.get("/registry/skills/fixture-maintainer/private-direct-skill/0.1.0/manifest.json")
        if private_manifest.status_code != 404:
            fail(f"expected anonymous private manifest to return 404, got {private_manifest.status_code}: {private_manifest.text}")

        grant_bundle = client.get(
            "/registry/catalog/distributions/fixture-maintainer/grant-listed-skill/0.1.0/skill.tar.gz",
            headers=grant_headers,
        )
        if grant_bundle.status_code != 200:
            fail(
                "expected grant catalog alias bundle access to succeed, "
                f"got {grant_bundle.status_code}: {grant_bundle.text}"
            )

        public_with_grant = client.get(
            "/registry/skills/fixture-maintainer/public-listed-skill/0.1.0/manifest.json",
            headers=grant_headers,
        )
        if public_with_grant.status_code != 404:
            fail(
                "expected scoped grant credential to remain bound to granted releases only, "
                f"got {public_with_grant.status_code}: {public_with_grant.text}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_registry_surfaces_are_audience_scoped()
    print("OK: private registry audience views checks passed")


if __name__ == "__main__":
    main()
