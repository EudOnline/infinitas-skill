#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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


def canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_prefixed(raw: str) -> str:
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def scenario_authoring_skill_draft_and_seal() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-authoring-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory
        from server.models import SkillDraft, SkillVersion

        client = TestClient(create_app())
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        create_skill_response = client.post(
            "/api/v1/skills",
            headers=headers,
            json={
                "slug": "private-first-authoring",
                "display_name": "Private First Authoring",
                "summary": "Authoring API fixture skill",
            },
        )
        if create_skill_response.status_code != 201:
            fail(
                "expected skill creation to return 201, "
                f"got {create_skill_response.status_code}: {create_skill_response.text}"
            )
        create_skill_payload = create_skill_response.json()
        skill_id = int(create_skill_payload["id"])

        get_skill_response = client.get(f"/api/v1/skills/{skill_id}", headers=headers)
        if get_skill_response.status_code != 200:
            fail(
                "expected skill read to return 200, "
                f"got {get_skill_response.status_code}: {get_skill_response.text}"
            )
        get_skill_payload = get_skill_response.json()
        if int(get_skill_payload["id"]) != skill_id:
            fail(f"expected skill id {skill_id}, got {get_skill_payload}")

        missing_base_version_response = client.post(
            f"/api/v1/skills/{skill_id}/drafts",
            headers=headers,
            json={
                "base_version_id": 9999,
                "content_ref": "git+https://example.com/private-first-authoring.git#0123456789abcdef0123456789abcdef01234567",
                "metadata": {"entrypoint": "SKILL.md"},
            },
        )
        if missing_base_version_response.status_code != 404:
            fail(
                "expected missing base version to return 404, "
                f"got {missing_base_version_response.status_code}: {missing_base_version_response.text}"
            )

        create_draft_response = client.post(
            f"/api/v1/skills/{skill_id}/drafts",
            headers=headers,
            json={
                "content_ref": "git+https://example.com/private-first-authoring.git#main",
                "metadata": {"entrypoint": "SKILL.md", "language": "zh-CN"},
            },
        )
        if create_draft_response.status_code != 201:
            fail(
                "expected draft creation to return 201, "
                f"got {create_draft_response.status_code}: {create_draft_response.text}"
            )
        create_draft_payload = create_draft_response.json()
        draft_id = int(create_draft_payload["id"])
        if create_draft_payload.get("state") != "open":
            fail(f"expected new draft state to be open, got {create_draft_payload}")

        patched_metadata = {
            "entrypoint": "SKILL.md",
            "language": "zh-CN",
            "manifest": {"name": "private-first-authoring", "version": "0.1.0"},
        }
        patch_draft_response = client.patch(
            f"/api/v1/drafts/{draft_id}",
            headers=headers,
            json={"metadata": patched_metadata},
        )
        if patch_draft_response.status_code != 200:
            fail(
                "expected draft patch to return 200, "
                f"got {patch_draft_response.status_code}: {patch_draft_response.text}"
            )
        patch_draft_payload = patch_draft_response.json()
        if patch_draft_payload.get("metadata") != patched_metadata:
            fail(f"expected patched metadata to round-trip, got {patch_draft_payload}")

        seal_with_mutable_ref_response = client.post(
            f"/api/v1/drafts/{draft_id}/seal",
            headers=headers,
            json={"version": "0.1.0"},
        )
        if seal_with_mutable_ref_response.status_code != 409:
            fail(
                "expected mutable git ref to be rejected during seal, "
                f"got {seal_with_mutable_ref_response.status_code}: {seal_with_mutable_ref_response.text}"
            )

        pinned_content_ref = "git+https://example.com/private-first-authoring.git#0123456789abcdef0123456789abcdef01234567"
        patch_content_ref_response = client.patch(
            f"/api/v1/drafts/{draft_id}",
            headers=headers,
            json={"content_ref": pinned_content_ref},
        )
        if patch_content_ref_response.status_code != 200:
            fail(
                "expected draft content_ref patch to return 200, "
                f"got {patch_content_ref_response.status_code}: {patch_content_ref_response.text}"
            )

        seal_response = client.post(
            f"/api/v1/drafts/{draft_id}/seal",
            headers=headers,
            json={"version": "0.1.0"},
        )
        if seal_response.status_code != 201:
            fail(f"expected seal to return 201, got {seal_response.status_code}: {seal_response.text}")
        seal_payload = seal_response.json()
        if seal_payload.get("version") != "0.1.0":
            fail(f"expected top-level sealed version 0.1.0 in response, got {seal_payload}")
        if seal_payload.get("draft", {}).get("state") != "sealed":
            fail(f"expected sealed draft state in response, got {seal_payload}")
        sealed_version = seal_payload.get("skill_version") or {}
        if sealed_version.get("version") != "0.1.0":
            fail(f"expected sealed version 0.1.0 in response, got {seal_payload}")

        session_factory = get_session_factory()
        with session_factory() as session:
            draft = session.get(SkillDraft, draft_id)
            if draft is None:
                fail("expected draft row to exist after seal")
            if draft.state != "sealed":
                fail(f"expected persisted draft state=sealed, got {draft.state!r}")

            version = session.scalar(select(SkillVersion).where(SkillVersion.created_from_draft_id == draft_id))
            if version is None:
                fail("expected skill version to be created from sealed draft")
            expected_content_digest = sha256_prefixed(pinned_content_ref)
            expected_metadata_digest = sha256_prefixed(canonical_json(patched_metadata))
            if version.content_digest != expected_content_digest:
                fail(
                    "expected content digest computed from frozen draft content, "
                    f"got {version.content_digest!r} expected {expected_content_digest!r}"
                )
            if version.metadata_digest != expected_metadata_digest:
                fail(
                    "expected metadata digest computed from frozen draft metadata, "
                    f"got {version.metadata_digest!r} expected {expected_metadata_digest!r}"
                )

        branched_draft_response = client.post(
            f"/api/v1/skills/{skill_id}/drafts",
            headers=headers,
            json={
                "base_version_id": int(sealed_version["id"]),
                "content_ref": "git+https://example.com/private-first-authoring.git#fedcba9876543210fedcba9876543210fedcba98",
                "metadata": {"entrypoint": "SKILL.md", "language": "zh-CN"},
            },
        )
        if branched_draft_response.status_code != 201:
            fail(
                "expected draft branching from existing version to return 201, "
                f"got {branched_draft_response.status_code}: {branched_draft_response.text}"
            )
        branched_draft_payload = branched_draft_response.json()
        if int(branched_draft_payload.get("base_version_id") or 0) != int(sealed_version["id"]):
            fail(f"expected branched draft base_version_id to round-trip, got {branched_draft_payload}")

        create_other_skill_response = client.post(
            "/api/v1/skills",
            headers=headers,
            json={
                "slug": "private-first-authoring-other",
                "display_name": "Private First Authoring Other",
                "summary": "Second skill for base version validation",
            },
        )
        if create_other_skill_response.status_code != 201:
            fail(
                "expected second skill creation to return 201, "
                f"got {create_other_skill_response.status_code}: {create_other_skill_response.text}"
            )
        other_skill_id = int(create_other_skill_response.json()["id"])
        cross_skill_base_version_response = client.post(
            f"/api/v1/skills/{other_skill_id}/drafts",
            headers=headers,
            json={
                "base_version_id": int(sealed_version["id"]),
                "content_ref": "git+https://example.com/private-first-authoring-other.git#00112233445566778899aabbccddeeff00112233",
                "metadata": {"entrypoint": "SKILL.md"},
            },
        )
        if cross_skill_base_version_response.status_code != 409:
            fail(
                "expected cross-skill base version to return 409, "
                f"got {cross_skill_base_version_response.status_code}: {cross_skill_base_version_response.text}"
            )

        patch_after_seal_response = client.patch(
            f"/api/v1/drafts/{draft_id}",
            headers=headers,
            json={"metadata": {"entrypoint": "CHANGED.md"}},
        )
        if patch_after_seal_response.status_code != 409:
            fail(
                "expected sealed draft to reject patch with 409, "
                f"got {patch_after_seal_response.status_code}: {patch_after_seal_response.text}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_authoring_skill_draft_and_seal()
    print("OK: private registry authoring api checks passed")


if __name__ == "__main__":
    main()
