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
    from server.db import get_engine, get_session_factory
    from server.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
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


def create_sealed_version(client, headers: dict[str, str]) -> tuple[int, int]:
    create_skill_response = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": "private-first-release",
            "display_name": "Private First Release",
            "summary": "Release API fixture skill",
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
            "content_ref": "git+https://example.com/private-first-release.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {
                "entrypoint": "SKILL.md",
                "language": "zh-CN",
                "manifest": {"name": "private-first-release", "version": "0.1.0"},
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
    return skill_id, version_id


def scenario_release_api_round_trip() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-release-api-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory
        from server.models import Job
        from server.worker import run_worker_loop

        client = TestClient(create_app())
        headers = {"Authorization": "Bearer fixture-maintainer-token"}
        _, version_id = create_sealed_version(client, headers)

        create_release_response = client.post(
            f"/api/v1/versions/{version_id}/releases",
            headers=headers,
        )
        if create_release_response.status_code != 201:
            fail(
                "expected release creation to return 201, "
                f"got {create_release_response.status_code}: {create_release_response.text}"
            )
        release_payload = create_release_response.json()
        release_id = int(release_payload["id"])
        if release_payload.get("state") != "preparing":
            fail(f"expected release state=preparing, got {release_payload}")

        session_factory = get_session_factory()
        with session_factory() as session:
            job = session.scalar(
                select(Job).where(Job.kind == "materialize_release").order_by(Job.id.desc())
            )
            if job is None:
                fail("expected materialize_release job to be queued")

        get_release_response = client.get(f"/api/v1/releases/{release_id}", headers=headers)
        if get_release_response.status_code != 200:
            fail(
                "expected release fetch to return 200, "
                f"got {get_release_response.status_code}: {get_release_response.text}"
            )
        if get_release_response.json().get("state") != "preparing":
            fail(f"expected fetched release state=preparing, got {get_release_response.json()}")

        list_artifacts_response = client.get(
            f"/api/v1/releases/{release_id}/artifacts",
            headers=headers,
        )
        if list_artifacts_response.status_code != 200:
            fail(
                "expected artifact listing to return 200, "
                f"got {list_artifacts_response.status_code}: {list_artifacts_response.text}"
            )
        if list_artifacts_response.json().get("items") != []:
            fail(
                "expected empty artifacts before materialization, "
                f"got {list_artifacts_response.json()}"
            )

        processed = run_worker_loop(limit=1)
        if processed != 1:
            fail(f"expected worker to process 1 job, got {processed}")

        finished_release_response = client.get(f"/api/v1/releases/{release_id}", headers=headers)
        if finished_release_response.status_code != 200:
            fail(
                "expected finished release fetch to return 200, "
                f"got {finished_release_response.status_code}: {finished_release_response.text}"
            )
        finished_release = finished_release_response.json()
        if finished_release.get("state") != "ready":
            fail(f"expected finished release state=ready, got {finished_release}")

        list_artifacts_response = client.get(
            f"/api/v1/releases/{release_id}/artifacts",
            headers=headers,
        )
        if list_artifacts_response.status_code != 200:
            fail(
                "expected finished artifact listing to return 200, "
                f"got {list_artifacts_response.status_code}: {list_artifacts_response.text}"
            )
        artifact_payload = list_artifacts_response.json()
        artifact_kinds = {item.get("kind") for item in artifact_payload.get("items") or []}
        if artifact_kinds != {"bundle", "manifest", "provenance", "signature"}:
            fail(f"expected four canonical artifact kinds, got {artifact_payload}")

        retry_response = client.post(
            f"/api/v1/versions/{version_id}/releases",
            headers=headers,
        )
        if retry_response.status_code not in (200, 409):
            fail(
                "expected repeat release request to be idempotent, "
                f"got {retry_response.status_code}: {retry_response.text}"
            )
        if retry_response.status_code == 200 and int(retry_response.json()["id"]) != release_id:
            fail(f"expected idempotent retry to return same release, got {retry_response.json()}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_repeat_release_request_rematerializes_legacy_ready_release() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-release-rematerialize-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from infinitas_skill.install.distribution import verify_distribution_manifest
        from server.app import create_app
        from server.worker import run_worker_loop

        client = TestClient(create_app())
        headers = {"Authorization": "Bearer fixture-maintainer-token"}
        _, version_id = create_sealed_version(client, headers)

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
            fail(f"expected worker to process 1 job, got {processed}")

        manifest_path = (
            tmpdir
            / "artifacts"
            / "skills"
            / "fixture-maintainer"
            / "private-first-release"
            / "0.1.0"
            / "manifest.json"
        )
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "kind": "private-skill-release-manifest",
                    "release_id": release_id,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        retry_response = client.post(
            f"/api/v1/versions/{version_id}/releases",
            headers=headers,
        )
        if retry_response.status_code != 200:
            fail(
                "expected repeat legacy release request to return 200, "
                f"got {retry_response.status_code}: {retry_response.text}"
            )

        processed = run_worker_loop(limit=1)
        if processed != 1:
            fail(f"expected rematerialization worker to process 1 job, got {processed}")

        verified = verify_distribution_manifest(
            manifest_path,
            root=tmpdir / "artifacts",
            attestation_root=ROOT,
        )
        if verified.get("verified") is not True:
            fail(f"expected rematerialized manifest to verify, got {verified!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_release_api_round_trip()
    scenario_repeat_release_request_rematerializes_legacy_ready_release()
    print("OK: private registry release api checks passed")


if __name__ == "__main__":
    main()
