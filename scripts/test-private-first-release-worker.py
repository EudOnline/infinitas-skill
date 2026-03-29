#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

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


def scenario_release_worker_only_processes_release_jobs() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-worker-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory
        from server.jobs import enqueue_job
        from server.models import Job, Release, User
        from server.repo_ops import RepoOpError
        from server.worker import process_job, run_worker_loop

        client = TestClient(create_app())
        factory = get_session_factory()
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        create_skill = client.post(
            "/api/v1/skills",
            headers=headers,
            json={"slug": "worker-skill", "display_name": "Worker Skill", "summary": "Worker summary"},
        )
        if create_skill.status_code != 201:
            fail(f"expected skill creation to return 201, got {create_skill.status_code}: {create_skill.text}")
        skill_id = int(create_skill.json()["id"])

        create_draft = client.post(
            f"/api/v1/skills/{skill_id}/drafts",
            headers=headers,
            json={
                "content_ref": "git+https://example.com/worker-skill.git#0123456789abcdef0123456789abcdef01234567",
                "metadata": {"entrypoint": "SKILL.md", "manifest": {"name": "worker-skill", "version": "0.1.0"}},
            },
        )
        if create_draft.status_code != 201:
            fail(f"expected draft creation to return 201, got {create_draft.status_code}: {create_draft.text}")
        draft_id = int(create_draft.json()["id"])

        seal = client.post(f"/api/v1/drafts/{draft_id}/seal", headers=headers, json={"version": "0.1.0"})
        if seal.status_code != 201:
            fail(f"expected seal to return 201, got {seal.status_code}: {seal.text}")
        version_id = int((seal.json().get("skill_version") or {})["id"])

        release_response = client.post(f"/api/v1/versions/{version_id}/releases", headers=headers)
        if release_response.status_code != 201:
            fail(
                f"expected release creation to return 201, got {release_response.status_code}: {release_response.text}"
            )
        release_id = int(release_response.json()["id"])

        processed = run_worker_loop(limit=1)
        if processed != 1:
            fail(f"expected worker loop to process exactly 1 materialize job, got {processed}")

        with factory() as session:
            release = session.get(Release, release_id)
            if release is None or release.state != "ready":
                fail(f"expected release {release_id} to be ready after worker loop, got {release!r}")

        with factory() as session:
            user = session.query(User).filter(User.username == "fixture-maintainer").one_or_none()
            if user is None:
                fail("expected bootstrap maintainer user")
            legacy_job = enqueue_job(
                session,
                kind="validate_submission",
                payload={"release_id": release_id},
                requested_by=user,
                release_id=release_id,
                note="legacy job kind should fail",
            )
            legacy_job_id = legacy_job.id

        try:
            process_job(legacy_job_id)
        except RepoOpError:
            pass
        else:
            fail("expected legacy worker job kind to raise RepoOpError")

        with factory() as session:
            failed_job = session.get(Job, legacy_job_id)
            if failed_job is None or failed_job.status != "failed":
                fail(f"expected unsupported worker job to be marked failed, got {failed_job!r}")
            if "unsupported job kind" not in (failed_job.error_message or ""):
                fail(f"expected unsupported job kind error message, got {failed_job.error_message!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_release_worker_only_processes_release_jobs()
    print("OK: private-first release worker checks passed")


if __name__ == "__main__":
    main()
