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
            }
        ]
    )
    os.environ["INFINITAS_MEMORY_BACKEND"] = "disabled"
    os.environ["INFINITAS_MEMORY_WRITE_ENABLED"] = "1"
    os.environ["INFINITAS_MEMORY_CONTEXT_ENABLED"] = "0"


def test_private_registry_lifecycle_emits_memory_writeback_audit_events() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-memory-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory
        from server.models import AuditEvent, ReviewCase
        from server.worker import run_worker_loop

        client = TestClient(create_app())
        session_factory = get_session_factory()
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        create_skill_response = client.post(
            "/api/v1/skills",
            headers=headers,
            json={
                "slug": "memory-flow-skill",
                "display_name": "Memory Flow Skill",
                "summary": "Memory flow summary",
            },
        )
        assert create_skill_response.status_code == 201, create_skill_response.text
        skill_id = int(create_skill_response.json()["id"])

        create_draft_response = client.post(
            f"/api/v1/skills/{skill_id}/drafts",
            headers=headers,
            json={
                "content_ref": "git+https://example.com/memory-flow-skill.git#0123456789abcdef0123456789abcdef01234567",
                "metadata": {
                    "entrypoint": "SKILL.md",
                    "language": "zh-CN",
                    "manifest": {"name": "memory-flow-skill", "version": "0.1.0"},
                },
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

        create_exposure_response = client.post(
            f"/api/v1/releases/{release_id}/exposures",
            headers=headers,
            json={
                "audience_type": "public",
                "listing_mode": "listed",
                "install_mode": "enabled",
                "requested_review_mode": "none",
            },
        )
        assert create_exposure_response.status_code == 201, create_exposure_response.text
        exposure_id = int(create_exposure_response.json()["id"])

        with session_factory() as session:
            review_case = session.scalar(
                select(ReviewCase).where(ReviewCase.exposure_id == exposure_id)
            )
            assert review_case is not None
            review_case_id = int(review_case.id)

        approve_response = client.post(
            f"/api/v1/review-cases/{review_case_id}/decisions",
            headers=headers,
            json={"decision": "approve", "note": "approved for memory flow"},
        )
        assert approve_response.status_code == 201, approve_response.text

        with session_factory() as session:
            events = session.scalars(
                select(AuditEvent)
                .where(AuditEvent.aggregate_type == "memory_writeback")
                .order_by(AuditEvent.id.asc())
            ).all()
            assert events, "expected lifecycle hooks to emit memory writeback audit events"

            lifecycle_events: set[str] = set()
            statuses: set[str] = set()
            for event in events:
                assert event.event_type.startswith("memory.writeback.")
                payload = json.loads(event.payload_json or "{}")
                lifecycle_event = str(payload.get("lifecycle_event") or "").strip()
                if lifecycle_event:
                    lifecycle_events.add(lifecycle_event)
                status = str(payload.get("status") or "").strip()
                if status:
                    statuses.add(status)

            assert {
                "task.authoring.create_draft",
                "task.authoring.seal_draft",
                "task.release.ready",
                "task.exposure.create",
                "task.review.approve",
                "task.exposure.activate",
            }.issubset(lifecycle_events)
            assert statuses.intersection({"stored", "skipped"})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
