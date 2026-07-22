from __future__ import annotations

import io
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers.hosted_content import build_skill_bundle, upload_skill_content

HEADERS = {"Authorization": "Bearer fixture-maintainer-token"}


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key-32chars-long-minimum"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
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


def _client(tmpdir: Path) -> TestClient:
    configure_env(tmpdir)
    from server.app import create_app

    return TestClient(create_app())


def _create_skill(client: TestClient, slug: str = "uploaded-skill") -> int:
    response = client.post(
        "/api/v1/skills",
        headers=HEADERS,
        json={
            "slug": slug,
            "display_name": slug.replace("-", " ").title(),
            "summary": "content storage fixture",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _archive(entries: list[tuple[tarfile.TarInfo, bytes | None]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for info, raw in entries:
            archive.addfile(info, io.BytesIO(raw) if raw is not None else None)
    return buffer.getvalue()


def _regular_member(path: str, raw: bytes = b"fixture") -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(path)
    info.size = len(raw)
    return info, raw


def test_upload_and_create_version_freezes_validated_content() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-content-test-"))
    try:
        client = _client(tmpdir)
        skill_id = _create_skill(client)
        content = upload_skill_content(client, skill_id, "uploaded-skill", "0.1.0", HEADERS)

        assert content["content_id"].startswith("cnt_")
        assert content["sha256"].startswith("sha256:")
        assert content["declared_version"] == "0.1.0"
        response = client.post(
            f"/api/v1/skills/{skill_id}/versions",
            headers=HEADERS,
            json={
                "version": "0.1.0",
                "content_id": content["content_id"],
            },
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["content_digest"] == content["sha256"]
        assert payload["sealed_manifest"]["content_id"] == content["content_id"]
        assert payload["sealed_manifest"]["content_mode"] == "uploaded_bundle"
        assert payload["sealed_manifest"]["metadata"]["name"] == "uploaded-skill"
        assert payload["sealed_manifest"]["metadata"]["version"] == "0.1.0"
        assert payload["sealed_manifest"]["metadata"]["quality_score"] == 73
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_upload_rejects_metadata_identity_outside_hosted_namespace() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-identity-test-"))
    try:
        client = _client(tmpdir)
        skill_id = _create_skill(client)
        bundle = build_skill_bundle(
            "uploaded-skill",
            "0.1.0",
            metadata_overrides={
                "publisher": "other-publisher",
                "qualified_name": "other-publisher/uploaded-skill",
            },
        )

        response = client.post(
            f"/api/v1/skills/{skill_id}/content",
            headers={**HEADERS, "Content-Type": "application/gzip"},
            content=bundle,
        )

        assert response.status_code == 422, response.text
        assert "must equal hosted namespace 'fixture-maintainer'" in response.text
        assert not any((tmpdir / "artifacts").rglob("*.tar.gz"))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.parametrize(
    "bundle",
    [
        b"not-a-tarball",
        _archive([_regular_member("../escape.txt")]),
        _archive([_regular_member("wrong-root/SKILL.md")]),
    ],
    ids=["invalid-archive", "path-traversal", "wrong-root"],
)
def test_upload_rejects_invalid_bundle(bundle: bytes) -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-invalid-test-"))
    try:
        client = _client(tmpdir)
        skill_id = _create_skill(client)
        response = client.post(
            f"/api/v1/skills/{skill_id}/content",
            headers={**HEADERS, "Content-Type": "application/gzip"},
            content=bundle,
        )
        assert response.status_code == 422, response.text
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.parametrize("link_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_upload_rejects_links(link_type: bytes) -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-link-test-"))
    try:
        client = _client(tmpdir)
        skill_id = _create_skill(client)
        info = tarfile.TarInfo("uploaded-skill/link")
        info.type = link_type
        info.linkname = "uploaded-skill/SKILL.md"
        response = client.post(
            f"/api/v1/skills/{skill_id}/content",
            headers={**HEADERS, "Content-Type": "application/gzip"},
            content=_archive([(info, None)]),
        )
        assert response.status_code == 422, response.text
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_content_is_skill_scoped_single_use_and_version_bound() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-scope-test-"))
    try:
        client = _client(tmpdir)
        first_skill = _create_skill(client)
        second_skill = _create_skill(client, "other-skill")
        content = upload_skill_content(client, first_skill, "uploaded-skill", "0.1.0", HEADERS)
        wrong_skill = client.post(
            f"/api/v1/skills/{second_skill}/versions",
            headers=HEADERS,
            json={"version": "0.1.0", "content_id": content["content_id"]},
        )
        assert wrong_skill.status_code == 404
        wrong_version = client.post(
            f"/api/v1/skills/{first_skill}/versions",
            headers=HEADERS,
            json={"version": "0.2.0", "content_id": content["content_id"]},
        )
        assert wrong_version.status_code == 409
        accepted = client.post(
            f"/api/v1/skills/{first_skill}/versions",
            headers=HEADERS,
            json={"version": "0.1.0", "content_id": content["content_id"]},
        )
        assert accepted.status_code == 201, accepted.text
        reused = client.post(
            f"/api/v1/skills/{first_skill}/versions",
            headers=HEADERS,
            json={"version": "0.1.1", "content_id": content["content_id"]},
        )
        assert reused.status_code == 409
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_legacy_content_fields_are_rejected() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-legacy-test-"))
    try:
        client = _client(tmpdir)
        skill_id = _create_skill(client)
        response = client.post(
            f"/api/v1/skills/{skill_id}/versions",
            headers=HEADERS,
            json={
                "version": "0.1.0",
                "content_id": "cnt_legacyfixture",
                "content_mode": "external_ref",
                "content_ref": "git+https://example.com/repo.git#deadbeef",
                "content_upload_token": "1",
            },
        )
        assert response.status_code == 422
        schema = client.get("/openapi.json").json()["components"]["schemas"]
        properties = schema["SkillVersionCreateRequest"]["properties"]
        assert set(properties) == {"version", "content_id"}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_list_skill_versions_requires_authentication() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-list-test-"))
    try:
        client = _client(tmpdir)
        skill_id = _create_skill(client)
        for version in ("0.1.0", "0.2.0"):
            content = upload_skill_content(client, skill_id, "uploaded-skill", version, HEADERS)
            response = client.post(
                f"/api/v1/skills/{skill_id}/versions",
                headers=HEADERS,
                json={"version": version, "content_id": content["content_id"]},
            )
            assert response.status_code == 201, response.text
        listed = client.get(f"/api/v1/skills/{skill_id}/versions", headers=HEADERS)
        assert [item["version"] for item in listed.json()] == ["0.2.0", "0.1.0"]
        assert client.get(f"/api/v1/skills/{skill_id}/versions").status_code == 401
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_upload_requires_gzip_content_type_and_installable_files() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-media-test-"))
    try:
        client = _client(tmpdir)
        skill_id = _create_skill(client)
        bundle = build_skill_bundle("uploaded-skill", "0.1.0")
        unsupported = client.post(
            f"/api/v1/skills/{skill_id}/content",
            headers=HEADERS,
            content=bundle,
        )
        assert unsupported.status_code == 415
        incomplete = _archive([_regular_member("uploaded-skill/SKILL.md")])
        invalid = client.post(
            f"/api/v1/skills/{skill_id}/content",
            headers={**HEADERS, "Content-Type": "application/gzip"},
            content=incomplete,
        )
        assert invalid.status_code == 422
        assert "_meta.json" in invalid.text
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
