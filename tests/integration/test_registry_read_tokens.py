from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.helpers.signing import add_allowed_signer, configure_git_ssh_signing


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _prepare_signing_repo(repo: Path, signing_key: Path) -> None:
    allowed_signers = repo / "config" / "allowed_signers"
    allowed_signers.write_text("", encoding="utf-8")
    add_allowed_signer(allowed_signers, identity="release-test", key_path=signing_key)

    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.name", "Registry Read Test"], cwd=repo)
    _run(["git", "config", "user.email", "registry@example.com"], cwd=repo)
    configure_git_ssh_signing(repo, signing_key)
    _run(["git", "add", "config/allowed_signers", "config/signing.json"], cwd=repo)
    _run(["git", "commit", "-m", "test: bootstrap signing config"], cwd=repo)


def _configure_env(monkeypatch, *, tmp_path: Path, repo: Path) -> Path:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
    monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(artifact_root))
    monkeypatch.setenv("INFINITAS_SERVER_REPO_PATH", str(repo))
    monkeypatch.setenv(
        "INFINITAS_REGISTRY_READ_TOKENS",
        json.dumps(["registry-reader-token"]),
    )
    monkeypatch.setenv(
        "INFINITAS_SERVER_BOOTSTRAP_USERS",
        json.dumps(
            [
                {
                    "username": "fixture-maintainer",
                    "display_name": "Fixture Maintainer",
                    "role": "maintainer",
                    "token": "fixture-maintainer-token",
                }
            ]
        ),
    )
    return artifact_root


def _configure_public_env(monkeypatch, *, tmp_path: Path, repo: Path) -> Path:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
    monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(artifact_root))
    monkeypatch.setenv("INFINITAS_SERVER_REPO_PATH", str(repo))
    monkeypatch.delenv("INFINITAS_REGISTRY_READ_TOKENS", raising=False)
    monkeypatch.setenv(
        "INFINITAS_SERVER_BOOTSTRAP_USERS",
        json.dumps(
            [
                {
                    "username": "fixture-maintainer",
                    "display_name": "Fixture Maintainer",
                    "role": "maintainer",
                    "token": "fixture-maintainer-token",
                }
            ]
        ),
    )
    return artifact_root


def _create_public_release(client: TestClient) -> tuple[int, str]:
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    create_skill = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": "registry-gated-skill",
            "display_name": "Registry Gated Skill",
            "summary": "Registry reader token fixture",
        },
    )
    assert create_skill.status_code == 201, create_skill.text
    skill_id = int(create_skill.json()["id"])

    create_draft = client.post(
        f"/api/v1/skills/{skill_id}/drafts",
        headers=headers,
        json={
            "content_ref": "git+https://example.com/registry-gated-skill.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {
                "entrypoint": "SKILL.md",
                "language": "zh-CN",
                "manifest": {"name": "registry-gated-skill", "version": "0.1.0"},
            },
        },
    )
    assert create_draft.status_code == 201, create_draft.text
    draft_id = int(create_draft.json()["id"])

    seal = client.post(
        f"/api/v1/drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "0.1.0"},
    )
    assert seal.status_code == 201, seal.text
    version_id = int((seal.json().get("skill_version") or {})["id"])

    release = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers=headers,
    )
    assert release.status_code == 201, release.text

    return int(release.json()["id"]), headers["Authorization"]


def _approve_exposure_review(
    client: TestClient,
    *,
    authorization: str,
    exposure_id: int,
) -> None:
    from server.db import get_session_factory
    from server.models import ReviewCase

    with get_session_factory()() as session:
        review_case = session.scalar(
            select(ReviewCase).where(ReviewCase.exposure_id == exposure_id)
        )
        assert review_case is not None, f"expected review case for exposure {exposure_id}"
        review_case_id = review_case.id

    decision = client.post(
        f"/api/v1/review-cases/{review_case_id}/decisions",
        headers={"Authorization": authorization},
        json={"decision": "approve", "note": "approve public registry exposure"},
    )
    assert decision.status_code == 201, decision.text


def test_registry_read_tokens_gate_registry_routes_without_breaking_user_credentials(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)

    from server.app import create_app
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    release_id, maintainer_authorization = _create_public_release(client)

    processed = run_worker_loop(limit=1)
    assert processed == 1

    headers = {"Authorization": maintainer_authorization}
    exposure = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers=headers,
        json={
            "audience_type": "public",
            "listing_mode": "listed",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert exposure.status_code == 201, exposure.text
    _approve_exposure_review(
        client,
        authorization=maintainer_authorization,
        exposure_id=int(exposure.json()["id"]),
    )

    anonymous = client.get("/registry/ai-index.json")
    assert anonymous.status_code == 401, anonymous.text

    wrong_token = client.get(
        "/registry/ai-index.json",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert wrong_token.status_code == 401, wrong_token.text

    reader_token = client.get(
        "/registry/ai-index.json",
        headers={"Authorization": "Bearer registry-reader-token"},
    )
    assert reader_token.status_code == 200, reader_token.text
    skills = reader_token.json().get("skills") or []
    assert any(item.get("name") == "registry-gated-skill" for item in skills)

    maintainer_token = client.get(
        "/registry/ai-index.json",
        headers={"Authorization": maintainer_authorization},
    )
    assert maintainer_token.status_code == 200, maintainer_token.text

    manifest = client.get(
        "/registry/skills/fixture-maintainer/registry-gated-skill/0.1.0/manifest.json",
        headers={"Authorization": "Bearer registry-reader-token"},
    )
    assert manifest.status_code == 200, manifest.text


def test_public_registry_ignores_invalid_cookie_and_bearer_token(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_public_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)

    from server.app import create_app
    from server.auth import AUTH_COOKIE_NAME
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    release_id, maintainer_authorization = _create_public_release(client)

    processed = run_worker_loop(limit=1)
    assert processed == 1

    exposure = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers={"Authorization": maintainer_authorization},
        json={
            "audience_type": "public",
            "listing_mode": "listed",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert exposure.status_code == 201, exposure.text
    _approve_exposure_review(
        client,
        authorization=maintainer_authorization,
        exposure_id=int(exposure.json()["id"]),
    )

    anonymous = client.get("/registry/ai-index.json")
    assert anonymous.status_code == 200, anonymous.text

    client.cookies.set(AUTH_COOKIE_NAME, "bogus-cookie")
    stale_cookie = client.get("/registry/ai-index.json")
    client.cookies.delete(AUTH_COOKIE_NAME)
    assert stale_cookie.status_code == 200, stale_cookie.text

    wrong_token = client.get(
        "/registry/ai-index.json",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert wrong_token.status_code == 200, wrong_token.text


def test_public_registry_hides_release_when_materialized_artifacts_are_missing(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    artifact_root = _configure_public_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)

    from server.app import create_app
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    release_id, maintainer_authorization = _create_public_release(client)

    processed = run_worker_loop(limit=1)
    assert processed == 1

    exposure = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers={"Authorization": maintainer_authorization},
        json={
            "audience_type": "public",
            "listing_mode": "listed",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert exposure.status_code == 201, exposure.text
    _approve_exposure_review(
        client,
        authorization=maintainer_authorization,
        exposure_id=int(exposure.json()["id"]),
    )

    manifest_path = (
        artifact_root
        / "skills"
        / "fixture-maintainer"
        / "registry-gated-skill"
        / "0.1.0"
        / "manifest.json"
    )
    assert manifest_path.exists(), f"expected manifest fixture at {manifest_path}"
    manifest_path.unlink()

    anonymous = client.get("/registry/ai-index.json")
    assert anonymous.status_code == 200, anonymous.text
    skills = anonymous.json().get("skills") or []
    assert not any(item.get("name") == "registry-gated-skill" for item in skills)

    catalog_public = client.get("/api/v1/catalog/public")
    assert catalog_public.status_code == 200, catalog_public.text
    items = catalog_public.json().get("items") or []
    assert not any(item.get("name") == "registry-gated-skill" for item in items)

    install_public = client.get(
        "/api/v1/install/public/fixture-maintainer/registry-gated-skill@0.1.0"
    )
    assert install_public.status_code == 404, install_public.text


def test_production_rejects_malformed_registry_read_tokens(monkeypatch, tmp_path: Path) -> None:
    from server.settings import get_settings

    monkeypatch.setenv("INFINITAS_SERVER_ENV", "production")
    monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "prod-secret-key")
    monkeypatch.setenv(
        "INFINITAS_SERVER_BOOTSTRAP_USERS",
        json.dumps(
            [
                {
                    "username": "fixture-maintainer",
                    "display_name": "Fixture Maintainer",
                    "role": "maintainer",
                    "token": "fixture-maintainer-token",
                }
            ]
        ),
    )
    monkeypatch.setenv("INFINITAS_REGISTRY_READ_TOKENS", "not-json")

    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="INFINITAS_REGISTRY_READ_TOKENS"):
        get_settings()


def test_production_rejects_non_array_registry_read_tokens(monkeypatch, tmp_path: Path) -> None:
    from server.settings import get_settings

    monkeypatch.setenv("INFINITAS_SERVER_ENV", "production")
    monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "prod-secret-key")
    monkeypatch.setenv(
        "INFINITAS_SERVER_BOOTSTRAP_USERS",
        json.dumps(
            [
                {
                    "username": "fixture-maintainer",
                    "display_name": "Fixture Maintainer",
                    "role": "maintainer",
                    "token": "fixture-maintainer-token",
                }
            ]
        ),
    )
    monkeypatch.setenv("INFINITAS_REGISTRY_READ_TOKENS", json.dumps({"bad": True}))

    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="INFINITAS_REGISTRY_READ_TOKENS"):
        get_settings()
