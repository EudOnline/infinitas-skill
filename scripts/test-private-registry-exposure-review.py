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
            }
        ]
    )


def create_ready_release(client, headers: dict[str, str]) -> int:
    from server.worker import run_worker_loop

    create_skill_response = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": "private-first-exposure",
            "display_name": "Private First Exposure",
            "summary": "Exposure and review fixture skill",
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
            "content_ref": "git+https://example.com/private-first-exposure.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {
                "entrypoint": "SKILL.md",
                "manifest": {"name": "private-first-exposure", "version": "0.1.0"},
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


def scenario_exposure_and_review_flow() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-exposure-review-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory
        from server.models import Exposure, ReviewCase

        client = TestClient(create_app())
        headers = {"Authorization": "Bearer fixture-maintainer-token"}
        release_id = create_ready_release(client, headers)

        private_response = client.post(
            f"/api/v1/releases/{release_id}/exposures",
            headers=headers,
            json={
                "audience_type": "private",
                "listing_mode": "direct_only",
                "install_mode": "enabled",
                "requested_review_mode": "none",
            },
        )
        if private_response.status_code != 201:
            fail(
                "expected private exposure creation to return 201, "
                f"got {private_response.status_code}: {private_response.text}"
            )
        private_exposure = private_response.json()
        if private_exposure.get("state") != "active":
            fail(f"expected private exposure state=active, got {private_exposure}")

        advisory_response = client.post(
            f"/api/v1/releases/{release_id}/exposures",
            headers=headers,
            json={
                "audience_type": "grant",
                "listing_mode": "direct_only",
                "install_mode": "enabled",
                "requested_review_mode": "advisory",
            },
        )
        if advisory_response.status_code != 201:
            fail(
                "expected advisory grant exposure creation to return 201, "
                f"got {advisory_response.status_code}: {advisory_response.text}"
            )
        advisory_exposure = advisory_response.json()
        if advisory_exposure.get("state") != "active":
            fail(f"expected advisory grant exposure state=active, got {advisory_exposure}")

        public_response = client.post(
            f"/api/v1/releases/{release_id}/exposures",
            headers=headers,
            json={
                "audience_type": "public",
                "listing_mode": "listed",
                "install_mode": "enabled",
                "requested_review_mode": "none",
            },
        )
        if public_response.status_code != 201:
            fail(
                "expected public exposure creation to return 201, "
                f"got {public_response.status_code}: {public_response.text}"
            )
        public_exposure = public_response.json()
        if public_exposure.get("state") != "review_open":
            fail(f"expected public exposure state=review_open, got {public_exposure}")

        session_factory = get_session_factory()
        with session_factory() as session:
            private_case = session.scalar(
                select(ReviewCase).where(ReviewCase.exposure_id == int(private_exposure["id"]))
            )
            if private_case is not None:
                fail("expected private exposure to avoid review case creation")

            advisory_case = session.scalar(
                select(ReviewCase).where(ReviewCase.exposure_id == int(advisory_exposure["id"]))
            )
            if advisory_case is None:
                fail("expected advisory grant exposure to open a review case")
            if advisory_case.mode != "advisory":
                fail(f"expected advisory review case mode, got {advisory_case.mode!r}")

            public_case = session.scalar(
                select(ReviewCase).where(ReviewCase.exposure_id == int(public_exposure["id"]))
            )
            if public_case is None:
                fail("expected public exposure to open a blocking review case")
            if public_case.mode != "blocking":
                fail(f"expected blocking public review case, got {public_case.mode!r}")
            public_case_id = public_case.id

        approve_response = client.post(
            f"/api/v1/review-cases/{public_case_id}/decisions",
            headers=headers,
            json={"decision": "approve", "note": "approved for publication"},
        )
        if approve_response.status_code != 201:
            fail(
                "expected public review approval to return 201, "
                f"got {approve_response.status_code}: {approve_response.text}"
            )

        with session_factory() as session:
            approved_exposure = session.get(Exposure, int(public_exposure["id"]))
            if approved_exposure is None or approved_exposure.state != "active":
                fail(f"expected approved public exposure to become active, got {approved_exposure}")

        second_public_response = client.post(
            f"/api/v1/releases/{release_id}/exposures",
            headers=headers,
            json={
                "audience_type": "public",
                "listing_mode": "listed",
                "install_mode": "enabled",
                "requested_review_mode": "none",
            },
        )
        if second_public_response.status_code != 201:
            fail(
                "expected second public exposure creation to return 201, "
                f"got {second_public_response.status_code}: {second_public_response.text}"
            )
        second_public_exposure = second_public_response.json()
        with session_factory() as session:
            second_public_case = session.scalar(
                select(ReviewCase).where(ReviewCase.exposure_id == int(second_public_exposure["id"]))
            )
            if second_public_case is None:
                fail("expected second public exposure to open a review case")
            second_public_case_id = second_public_case.id

        reject_response = client.post(
            f"/api/v1/review-cases/{second_public_case_id}/decisions",
            headers=headers,
            json={"decision": "reject", "note": "not ready"},
        )
        if reject_response.status_code != 201:
            fail(
                "expected public review rejection to return 201, "
                f"got {reject_response.status_code}: {reject_response.text}"
            )

        with session_factory() as session:
            rejected_exposure = session.get(Exposure, int(second_public_exposure["id"]))
            if rejected_exposure is None:
                fail("expected rejected public exposure row to exist")
            if rejected_exposure.state == "active":
                fail(f"expected rejected public exposure to stay inactive, got {rejected_exposure.state!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_exposure_and_review_flow()
    print("OK: private registry exposure and review checks passed")


if __name__ == "__main__":
    main()
