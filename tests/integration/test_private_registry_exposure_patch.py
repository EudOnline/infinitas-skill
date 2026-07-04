from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from tests.helpers.signing import add_allowed_signer, configure_git_ssh_signing


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key-32chars-long-minimum"
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


def _prepare_signing_repo(repo: Path, signing_key: Path) -> None:
    import subprocess

    allowed_signers = repo / "config" / "allowed_signers"
    allowed_signers.write_text("", encoding="utf-8")
    add_allowed_signer(allowed_signers, identity="release-test", key_path=signing_key)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Registry Test"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "registry@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    configure_git_ssh_signing(repo, signing_key)
    subprocess.run(
        ["git", "add", "config/allowed_signers", "config/signing.json"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "test: bootstrap signing config"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
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


def create_ready_release(client: TestClient, headers: dict[str, str], *, slug: str) -> int:
    from server.worker import run_worker_loop

    create_skill = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": slug,
            "display_name": "Exposure Patch Skill",
            "summary": "Exposure patch fixture",
        },
    )
    assert create_skill.status_code == 201, create_skill.text
    skill_id = int(create_skill.json()["id"])

    create_version = client.post(
        f"/api/v1/skills/{skill_id}/versions",
        headers=headers,
        json={
            "version": "0.1.0",
            "content_ref": f"git+https://example.com/{slug}.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {"entrypoint": "SKILL.md"},
        },
    )
    assert create_version.status_code == 201, create_version.text
    version_id = int(create_version.json()["id"])

    create_release = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers=headers,
    )
    assert create_release.status_code == 201, create_release.text
    release_id = int(create_release.json()["id"])

    processed = run_worker_loop(limit=5)
    assert processed >= 1
    return release_id


def test_patch_exposure_rejects_requested_review_mode_mutation(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    configure_env(tmp_path)
    os.environ["INFINITAS_SERVER_REPO_PATH"] = str(temp_repo_copy)

    from server.app import create_app

    client = TestClient(create_app())
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    release_id = create_ready_release(client, headers, slug="exposure-patch-skill")

    create_exposure = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers=headers,
        json={
            "audience_type": "grant",
            "listing_mode": "listed",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert create_exposure.status_code == 201, create_exposure.text
    exposure = create_exposure.json()

    patch_response = client.patch(
        f"/api/v1/exposures/{exposure['id']}",
        headers=headers,
        json={"requested_review_mode": "blocking"},
    )

    assert patch_response.status_code == 409, patch_response.text
    assert "requested_review_mode" in patch_response.text

    get_response = client.get(
        f"/api/v1/releases/{release_id}",
        headers=headers,
    )
    assert get_response.status_code == 200, get_response.text


def test_exposure_endpoints_reject_unknown_listing_and_install_modes(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    configure_env(tmp_path)
    os.environ["INFINITAS_SERVER_REPO_PATH"] = str(temp_repo_copy)

    from server.app import create_app

    client = TestClient(create_app())
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    release_id = create_ready_release(client, headers, slug="exposure-mode-skill")

    create_response = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers=headers,
        json={
            "audience_type": "grant",
            "listing_mode": "mystery",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert create_response.status_code == 422, create_response.text

    valid_exposure = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers=headers,
        json={
            "audience_type": "grant",
            "listing_mode": "listed",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert valid_exposure.status_code == 201, valid_exposure.text
    exposure_id = int(valid_exposure.json()["id"])

    patch_response = client.patch(
        f"/api/v1/exposures/{exposure_id}",
        headers=headers,
        json={"install_mode": "surprise"},
    )
    assert patch_response.status_code == 422, patch_response.text


def test_create_exposure_normalizes_requested_review_mode_by_audience(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    configure_env(tmp_path)
    os.environ["INFINITAS_SERVER_REPO_PATH"] = str(temp_repo_copy)

    from server.app import create_app

    client = TestClient(create_app())
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    release_id = create_ready_release(client, headers, slug="exposure-normalize-skill")

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
    assert public_response.status_code == 201, public_response.text
    assert public_response.json()["requested_review_mode"] == "blocking"
    assert public_response.json()["review_requirement"] == "blocking"

    authenticated_response = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers=headers,
        json={
            "audience_type": "authenticated",
            "listing_mode": "listed",
            "install_mode": "enabled",
            "requested_review_mode": "advisory",
        },
    )
    assert authenticated_response.status_code == 201, authenticated_response.text
    assert authenticated_response.json()["requested_review_mode"] == "none"
    assert authenticated_response.json()["review_requirement"] == "none"
