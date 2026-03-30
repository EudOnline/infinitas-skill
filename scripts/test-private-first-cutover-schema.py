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


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="infinitas-private-first-cutover-schema-") as tmp:
        tmpdir = Path(tmp)
        db_path = tmpdir / "server.db"
        repo_path = tmpdir / "repo"
        artifact_path = tmpdir / "artifacts"
        lock_path = tmpdir / "repo.lock"
        repo_path.mkdir(parents=True, exist_ok=True)
        artifact_path.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.update(
            {
                "INFINITAS_SERVER_DATABASE_URL": f"sqlite:///{db_path}",
                "INFINITAS_SERVER_REPO_PATH": str(repo_path),
                "INFINITAS_SERVER_ARTIFACT_PATH": str(artifact_path),
                "INFINITAS_SERVER_REPO_LOCK_PATH": str(lock_path),
            }
        )

        result = run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env)
        if result.returncode != 0:
            fail(
                "alembic upgrade head failed.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

        expected_tables = {
            "users",
            "principals",
            "teams",
            "team_memberships",
            "service_principals",
            "skills",
            "skill_drafts",
            "skill_versions",
            "releases",
            "artifacts",
            "exposures",
            "review_policies",
            "review_cases",
            "review_decisions",
            "access_grants",
            "credentials",
            "audit_events",
            "jobs",
            "alembic_version",
        }
        forbidden_tables = {"submissions", "reviews"}

        with sqlite3.connect(db_path) as conn:
            missing = sorted(table for table in expected_tables if not table_exists(conn, table))
            if missing:
                fail(f"expected canonical cutover tables to exist, missing: {missing}")

            lingering = sorted(table for table in forbidden_tables if table_exists(conn, table))
            if lingering:
                fail(f"expected legacy workflow tables to be removed, still present: {lingering}")

            job_columns = table_columns(conn, "jobs")
            if "release_id" not in job_columns:
                fail(f"expected jobs table to include release_id, got columns: {sorted(job_columns)}")
            if "submission_id" in job_columns:
                fail(f"expected jobs table to drop submission_id, got columns: {sorted(job_columns)}")

    print("OK: private-first cutover schema checks passed")


if __name__ == "__main__":
    main()
