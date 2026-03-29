#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(cmd: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def make_runtime_env(db_path: Path, repo_path: Path, artifact_path: Path, lock_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "INFINITAS_SERVER_DATABASE_URL": f"sqlite:///{db_path}",
            "INFINITAS_SERVER_REPO_PATH": str(repo_path),
            "INFINITAS_SERVER_ARTIFACT_PATH": str(artifact_path),
            "INFINITAS_SERVER_REPO_LOCK_PATH": str(lock_path),
            "INFINITAS_REGISTRY_READ_TOKENS": json.dumps(["registry-reader-token"]),
        }
    )
    return env


def write_release_artifact(artifact_root: Path, publisher: str, skill: str, version: str) -> None:
    artifact_dir = artifact_root / "skills" / publisher / skill / version
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps({"publisher": publisher, "skill": skill, "version": version}),
        encoding="utf-8",
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="infinitas-access-policy-") as tmp:
        tmpdir = Path(tmp)
        db_path = tmpdir / "server.db"
        repo_path = tmpdir / "repo"
        artifact_path = tmpdir / "artifacts"
        lock_path = tmpdir / "repo.lock"
        repo_path.mkdir(parents=True, exist_ok=True)
        artifact_path.mkdir(parents=True, exist_ok=True)
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path)
        os.environ.update(env)

        upgrade = run(["uv", "run", "alembic", "upgrade", "head"], env=env)
        if upgrade.returncode != 0:
            fail(
                "alembic upgrade head failed.\n"
                f"stdout:\n{upgrade.stdout}\n"
                f"stderr:\n{upgrade.stderr}"
            )

        from fastapi.testclient import TestClient
        from server import db as db_module
        from server.app import create_app
        from server.models import Namespace, Release, Skill, SkillVersion
        from server.modules.access.service import create_release_exposure
        from server.settings import get_settings

        get_settings.cache_clear()
        db_module.get_engine.cache_clear()
        db_module.get_session_factory.cache_clear()
        db_module.ensure_database_ready()

        write_release_artifact(artifact_path, "core", "deploy-skill", "1.0.0")
        write_release_artifact(artifact_path, "core", "deploy-skill", "2.0.0")
        write_release_artifact(artifact_path, "core", "deploy-skill", "3.0.0")

        factory = db_module.get_session_factory()
        with factory() as session:
            namespace = Namespace(slug="core")
            session.add(namespace)
            session.flush()

            skill = Skill(namespace_id=namespace.id, slug="deploy-skill")
            session.add(skill)
            session.flush()

            private_version = SkillVersion(skill_id=skill.id, version="1.0.0", payload_json='{"release":"1.0.0"}')
            grant_version = SkillVersion(skill_id=skill.id, version="2.0.0", payload_json='{"release":"2.0.0"}')
            public_version = SkillVersion(skill_id=skill.id, version="3.0.0", payload_json='{"release":"3.0.0"}')
            session.add_all([private_version, grant_version, public_version])
            session.flush()

            private_release = Release(skill_version_id=private_version.id, state="published")
            grant_release = Release(skill_version_id=grant_version.id, state="published")
            public_release = Release(skill_version_id=public_version.id, state="published")
            session.add_all([private_release, grant_release, public_release])
            session.flush()

            private_exposure, private_case, _, _ = create_release_exposure(session, private_release, mode="private")
            _, _, _, credential = create_release_exposure(
                session,
                grant_release,
                mode="grant",
                credential_token="grant-release-token",
            )
            public_exposure, public_case, _, _ = create_release_exposure(session, public_release, mode="public")
            session.commit()

            assert private_exposure.review_requirement == "none"
            assert private_case is None
            assert public_exposure.review_requirement == "blocking"
            assert public_case.status == "pending"
            assert credential is not None

        app = create_app()
        with TestClient(app) as client:
            allowed = client.get(
                "/registry/skills/core/deploy-skill/2.0.0/manifest.json",
                headers={"Authorization": "Bearer grant-release-token"},
            )
            if allowed.status_code != 200:
                fail(f"expected grant credential to read granted release, got {allowed.status_code}: {allowed.text}")

            denied = client.get(
                "/registry/skills/core/deploy-skill/1.0.0/manifest.json",
                headers={"Authorization": "Bearer grant-release-token"},
            )
            assert denied.status_code == 403

            legacy_me = client.get(
                "/api/v1/me",
                headers={"Authorization": "Bearer dev-maintainer-token"},
            )
            assert legacy_me.status_code == 200

    print("OK: private registry access policy checks passed")


if __name__ == "__main__":
    main()
