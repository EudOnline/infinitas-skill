from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _alembic_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        INFINITAS_SERVER_ENV="test",
        INFINITAS_SERVER_SECRET_KEY="test-secret-key",
        INFINITAS_SERVER_DATABASE_URL=f"sqlite:///{tmp_path / 'metadata.db'}",
        INFINITAS_SERVER_BOOTSTRAP_USERS="[]",
        PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "src")]),
    )
    return env


def _run_alembic(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def test_single_initial_migration_round_trips_empty_database(tmp_path: Path) -> None:
    migration_files = sorted((ROOT / "alembic" / "versions").glob("*.py"))
    assert [path.name for path in migration_files] == ["0001_initial.py"]

    env = _alembic_env(tmp_path)
    upgrade = _run_alembic("upgrade", "head", env=env)
    assert upgrade.returncode == 0, upgrade.stderr

    check = _run_alembic("check", env=env)
    assert check.returncode == 0, check.stderr

    downgrade = _run_alembic("downgrade", "base", env=env)
    assert downgrade.returncode == 0, downgrade.stderr

    database_path = tmp_path / "metadata.db"
    with closing(sqlite3.connect(database_path)) as connection:
        remaining_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT IN ('alembic_version', 'sqlite_sequence')"
            )
        }
    assert not remaining_tables


def test_model_tables_sort_without_cycles() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error",
            "-c",
            "from server.model_base import Base; "
            "import server.model_registry; "
            "list(Base.metadata.sorted_tables)",
        ],
        cwd=ROOT,
        env=dict(
            os.environ,
            PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "src")]),
        ),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
