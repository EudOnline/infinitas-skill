#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
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


def table_exists(db_path: Path, table_name: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table_name,),
        ).fetchone()
    return row is not None


def make_runtime_env(db_path: Path, repo_path: Path, artifact_path: Path, lock_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "INFINITAS_SERVER_DATABASE_URL": f"sqlite:///{db_path}",
            "INFINITAS_SERVER_REPO_PATH": str(repo_path),
            "INFINITAS_SERVER_ARTIFACT_PATH": str(artifact_path),
            "INFINITAS_SERVER_REPO_LOCK_PATH": str(lock_path),
        }
    )
    return env


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="infinitas-release-graph-") as tmp:
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

        from server import db as db_module
        from server.models import Artifact, Namespace, Release, Skill, SkillDraft, SkillVersion
        from server.settings import get_settings

        get_settings.cache_clear()
        db_module.get_engine.cache_clear()
        db_module.get_session_factory.cache_clear()
        db_module.ensure_database_ready()

        factory = db_module.get_session_factory()
        with factory() as session:
            namespace = Namespace(slug="core")
            session.add(namespace)
            session.flush()

            skill = Skill(namespace_id=namespace.id, slug="deploy-skill")
            session.add(skill)
            session.flush()

            draft = SkillDraft(skill_id=skill.id, state="draft", payload_json="{}")
            session.add(draft)
            session.flush()

            version = SkillVersion(skill_id=skill.id, version="1.0.0", payload_json='{"release":"1.0.0"}')
            session.add(version)
            session.flush()

            release = Release(skill_version_id=version.id, state="published")
            session.add(release)
            session.flush()

            artifact = Artifact(
                release_id=release.id,
                kind="manifest",
                digest="sha256:abc123",
                path="catalog/core/deploy-skill/1.0.0/manifest.json",
            )
            session.add(artifact)
            session.commit()

            assert release.skill_version_id == version.id
            assert release.skill_version.version == "1.0.0"
            assert artifact.release_id == release.id
            assert skill.namespace_id == namespace.id
            assert draft.skill_id == skill.id

        for table_name in (
            "users",
            "submissions",
            "reviews",
            "jobs",
            "namespaces",
            "skills",
            "skill_drafts",
            "skill_versions",
            "releases",
            "artifacts",
        ):
            if not table_exists(db_path, table_name):
                fail(f"expected table {table_name!r} in {db_path}")

    print("OK: private registry release graph checks passed")


if __name__ == "__main__":
    main()
