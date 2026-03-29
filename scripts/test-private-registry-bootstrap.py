#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AUTO_STAMP_REFUSAL = "refusing to auto-stamp"
BOOTSTRAP_REVISION = "20260329_0001"
LEGACY_INDEX_SPECS = (
    ("users", "users_token", ("token",), True),
    ("users", "users_username", ("username",), True),
    ("submissions", "submissions_skill_name", ("skill_name",), False),
    ("submissions", "submissions_status", ("status",), False),
    ("reviews", "reviews_status", ("status",), False),
    ("reviews", "reviews_submission_id", ("submission_id",), False),
    ("jobs", "jobs_kind", ("kind",), False),
    ("jobs", "jobs_status", ("status",), False),
    ("jobs", "jobs_submission_id", ("submission_id",), False),
)


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


def runtime_paths(tmpdir: Path) -> tuple[Path, Path, Path, Path]:
    db_path = tmpdir / "server.db"
    repo_path = tmpdir / "repo"
    artifact_path = tmpdir / "artifacts"
    lock_path = tmpdir / "repo.lock"
    repo_path.mkdir(parents=True, exist_ok=True)
    artifact_path.mkdir(parents=True, exist_ok=True)
    return db_path, repo_path, artifact_path, lock_path


def run_ensure_database_ready(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "uv",
            "run",
            "python3",
            "-c",
            (
                "from server import db as db_module; "
                "from server.settings import get_settings; "
                "get_settings.cache_clear(); "
                "db_module.get_engine.cache_clear(); "
                "db_module.get_session_factory.cache_clear(); "
                "db_module.ensure_database_ready()"
            ),
        ],
        env=env,
    )


def assert_auto_stamp_refused(db_path: Path, env: dict[str, str], *, case_name: str) -> None:
    result = run_ensure_database_ready(env)
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 0:
        fail(f"expected {case_name} to fail safe-stamp validation")
    if AUTO_STAMP_REFUSAL not in output:
        fail(
            f"expected {case_name} failure to mention auto-stamp refusal.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    if table_exists(db_path, "alembic_version"):
        fail(f"expected {case_name} to remain unstamped")


def assert_auto_stamp_succeeds(db_path: Path, env: dict[str, str], *, case_name: str) -> None:
    result = run_ensure_database_ready(env)
    if result.returncode != 0:
        fail(
            f"expected {case_name} to stamp and boot successfully.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    if not table_exists(db_path, "alembic_version"):
        fail(f"expected {case_name} to write alembic_version")
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if row is None or row[0] != BOOTSTRAP_REVISION:
        fail(f"expected {case_name} to stamp {BOOTSTRAP_REVISION}, got {row!r}")
    if user_count != 2:
        fail(f"expected {case_name} to seed 2 bootstrap users, got {user_count}")


def create_minimal_legacy_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE submissions (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE reviews (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY)")
        conn.commit()


def create_legacy_schema(
    db_path: Path,
    *,
    include_indexes: bool,
    include_foreign_keys: bool,
    role_nullable: bool = False,
    index_prefix: str = "ix_",
) -> None:
    role_clause = "role VARCHAR(32)," if role_nullable else "role VARCHAR(32) NOT NULL,"
    submissions_fk = ""
    reviews_fk = ""
    jobs_fk = ""
    if include_foreign_keys:
        submissions_fk = """
            ,
            FOREIGN KEY(created_by_user_id) REFERENCES users (id),
            FOREIGN KEY(updated_by_user_id) REFERENCES users (id)
        """
        reviews_fk = """
            ,
            FOREIGN KEY(submission_id) REFERENCES submissions (id),
            FOREIGN KEY(requested_by_user_id) REFERENCES users (id),
            FOREIGN KEY(reviewed_by_user_id) REFERENCES users (id)
        """
        jobs_fk = """
            ,
            FOREIGN KEY(submission_id) REFERENCES submissions (id),
            FOREIGN KEY(requested_by_user_id) REFERENCES users (id)
        """

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            f"""
            CREATE TABLE users (
                id INTEGER NOT NULL PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                display_name VARCHAR(200) NOT NULL,
                {role_clause}
                token VARCHAR(255) NOT NULL,
                light_bg_id VARCHAR(64),
                dark_bg_id VARCHAR(64),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );

            CREATE TABLE submissions (
                id INTEGER NOT NULL PRIMARY KEY,
                skill_name VARCHAR(200) NOT NULL,
                publisher VARCHAR(200) NOT NULL,
                status VARCHAR(64) NOT NULL,
                payload_json TEXT NOT NULL,
                payload_summary TEXT NOT NULL,
                status_log_json TEXT NOT NULL,
                created_by_user_id INTEGER,
                updated_by_user_id INTEGER,
                review_requested_at DATETIME,
                approved_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
                {submissions_fk}
            );

            CREATE TABLE reviews (
                id INTEGER NOT NULL PRIMARY KEY,
                submission_id INTEGER NOT NULL,
                status VARCHAR(64) NOT NULL,
                note TEXT NOT NULL,
                requested_by_user_id INTEGER,
                reviewed_by_user_id INTEGER,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
                {reviews_fk}
            );

            CREATE TABLE jobs (
                id INTEGER NOT NULL PRIMARY KEY,
                kind VARCHAR(100) NOT NULL,
                status VARCHAR(64) NOT NULL,
                payload_json TEXT NOT NULL,
                submission_id INTEGER,
                requested_by_user_id INTEGER,
                note TEXT NOT NULL,
                log TEXT NOT NULL,
                started_at DATETIME,
                finished_at DATETIME,
                error_message TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
                {jobs_fk}
            );
            """
        )
        if include_indexes:
            for table_name, suffix, columns, unique in LEGACY_INDEX_SPECS:
                unique_sql = "UNIQUE " if unique else ""
                index_name = f"{index_prefix}{suffix}"
                column_sql = ", ".join(columns)
                conn.execute(f"CREATE {unique_sql}INDEX {index_name} ON {table_name} ({column_sql})")
        conn.commit()


def create_create_all_legacy_schema(db_path: Path) -> None:
    from sqlalchemy import create_engine

    from server.models import Base

    engine = create_engine(f"sqlite:///{db_path}", future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="infinitas-bootstrap-") as tmp:
        tmpdir = Path(tmp)
        db_path, repo_path, artifact_path, lock_path = runtime_paths(tmpdir)
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path)

        upgrade = run(["uv", "run", "alembic", "upgrade", "head"], env=env)
        if upgrade.returncode != 0:
            fail(
                "alembic upgrade head failed.\n"
                f"stdout:\n{upgrade.stdout}\n"
                f"stderr:\n{upgrade.stderr}"
            )

        # Import after env is prepared so server settings pick up temporary paths.
        from fastapi.testclient import TestClient
        from server import db as db_module
        from server.app import create_app
        from server.settings import get_settings

        get_settings.cache_clear()
        db_module.get_engine.cache_clear()
        db_module.get_session_factory.cache_clear()
        db_module.ensure_database_ready()

        for table_name in ("users", "submissions", "reviews", "jobs", "alembic_version"):
            if not table_exists(db_path, table_name):
                fail(f"expected table {table_name!r} in {db_path}")

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/healthz")
        if response.status_code != 200:
            fail(f"expected GET /healthz to return 200, got {response.status_code}: {response.text}")

    with tempfile.TemporaryDirectory(prefix="infinitas-legacy-bootstrap-") as tmp:
        tmpdir = Path(tmp)
        db_path, repo_path, artifact_path, lock_path = runtime_paths(tmpdir)
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path)
        create_minimal_legacy_schema(db_path)
        assert_auto_stamp_refused(db_path, env, case_name="minimal incompatible legacy schema")

    with tempfile.TemporaryDirectory(prefix="infinitas-legacy-index-drift-") as tmp:
        tmpdir = Path(tmp)
        db_path, repo_path, artifact_path, lock_path = runtime_paths(tmpdir)
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path)
        create_legacy_schema(db_path, include_indexes=False, include_foreign_keys=True)
        assert_auto_stamp_refused(db_path, env, case_name="legacy schema missing only indexes")

    with tempfile.TemporaryDirectory(prefix="infinitas-legacy-fk-drift-") as tmp:
        tmpdir = Path(tmp)
        db_path, repo_path, artifact_path, lock_path = runtime_paths(tmpdir)
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path)
        create_legacy_schema(db_path, include_indexes=True, include_foreign_keys=False)
        assert_auto_stamp_refused(db_path, env, case_name="legacy schema missing only foreign keys")

    with tempfile.TemporaryDirectory(prefix="infinitas-legacy-column-drift-") as tmp:
        tmpdir = Path(tmp)
        db_path, repo_path, artifact_path, lock_path = runtime_paths(tmpdir)
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path)
        create_legacy_schema(db_path, include_indexes=True, include_foreign_keys=True, role_nullable=True)
        assert_auto_stamp_refused(db_path, env, case_name="legacy schema with column metadata drift")

    with tempfile.TemporaryDirectory(prefix="infinitas-legacy-custom-indexes-") as tmp:
        tmpdir = Path(tmp)
        db_path, repo_path, artifact_path, lock_path = runtime_paths(tmpdir)
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path)
        create_legacy_schema(
            db_path,
            include_indexes=True,
            include_foreign_keys=True,
            index_prefix="legacy_",
        )
        assert_auto_stamp_succeeds(db_path, env, case_name="legacy schema with custom index names")

    with tempfile.TemporaryDirectory(prefix="infinitas-legacy-create-all-") as tmp:
        tmpdir = Path(tmp)
        db_path, repo_path, artifact_path, lock_path = runtime_paths(tmpdir)
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path)
        create_create_all_legacy_schema(db_path)
        assert_auto_stamp_succeeds(db_path, env, case_name="legacy schema created via Base.metadata.create_all()")

    print("OK: private registry bootstrap checks passed")


if __name__ == "__main__":
    main()
