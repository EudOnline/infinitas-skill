from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import server.model_registry  # noqa: F401
from server.model_base import Base
from server.modules.jobs.models import Job
from tests.fixtures.repo_state import create_repo_state
from tests.helpers.ops_support.server_ops import HealthServer
from tests.helpers.ops_support.server_ops import run_command as shared_run_command

ROOT = Path(__file__).resolve().parents[2]

# Ensure subprocess CLI invocations use the project venv even when this test
# file is imported by a system Python interpreter.
_VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"
if _VENV_PYTHON.exists() and sys.executable != str(_VENV_PYTHON):
    sys.executable = str(_VENV_PYTHON)


def _run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    expect: int | None = 0,
    env: dict[str, str] | None = None,
):
    try:
        return shared_run_command(command, cwd=cwd, expect=expect, env=env)
    except SystemExit as exc:
        raise AssertionError(str(exc).removeprefix("FAIL: ")) from exc


def _run_cli(args: list[str], *, expect: int | None = 0, env: dict[str, str] | None = None):
    merged_env = os.environ.copy()
    if env is not None:
        merged_env.update(env)
    existing_pythonpath = merged_env.get("PYTHONPATH", "")
    merged_env["PYTHONPATH"] = (
        f"{ROOT / 'src'}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(ROOT / "src")
    )
    return _run(
        [sys.executable, "-m", "infinitas_skill.cli.main", *args], expect=expect, env=merged_env
    )


def _load_json_output(result, *, label: str) -> dict:
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        raise AssertionError(
            f"{label} did not emit JSON output: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        ) from exc


def assert_server_cli_help_lists_maintained_subcommands() -> None:
    result = _run_cli(["server", "--help"], expect=0)
    help_text = result.stdout + result.stderr
    for command in [
        "healthcheck",
        "backup",
        "render-systemd",
        "prune-backups",
        "worker",
        "inspect-state",
    ]:
        assert command in help_text, f"expected {command!r} in infinitas server help"


def assert_server_ops_split_into_modules() -> None:
    from infinitas_skill.server import ops

    ops_path = ROOT / "src" / "infinitas_skill" / "server" / "ops.py"
    line_count = len(ops_path.read_text(encoding="utf-8").splitlines())
    assert line_count <= 550, (
        f"expected src/infinitas_skill/server/ops.py to stay within 550 lines after extraction, got {line_count}"
    )
    assert ops.run_server_healthcheck.__module__ == "infinitas_skill.server.health"
    assert ops.run_server_prune_backups.__module__ == "infinitas_skill.server.backup"


def assert_server_healthcheck_reports_expected_summary() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-cli-server-health-"))
    try:
        repo_state = create_repo_state(tmpdir)
        with HealthServer() as base_url:
            args = [
                "--api-url",
                base_url,
                "--repo-path",
                str(repo_state.repo),
                "--artifact-path",
                str(repo_state.artifact_dir),
                "--database-url",
                f"sqlite:///{repo_state.db_path}",
                "--json",
            ]
            cli = _run_cli(["server", "healthcheck", *args], expect=0)

        cli_payload = _load_json_output(cli, label="infinitas server healthcheck")
        assert cli_payload.get("ok") is True
        assert cli_payload.get("api", {}).get("ok") is True
        assert cli_payload.get("api", {}).get("url", "").endswith("/api/v1/system/healthz")
        assert cli_payload.get("repo", {}).get("clean") is True
        assert cli_payload.get("artifacts", {}).get("ai_index") is True
        assert cli_payload.get("database", {}).get("kind") == "sqlite"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_server_cli_help_lists_maintained_subcommands() -> None:
    assert_server_cli_help_lists_maintained_subcommands()


def test_server_ops_split_into_smaller_modules() -> None:
    assert_server_ops_split_into_modules()


def test_server_healthcheck_reports_expected_summary() -> None:
    assert_server_healthcheck_reports_expected_summary()


def test_server_inspect_state_reports_job_lease_health(tmp_path: Path) -> None:
    db_path = tmp_path / "inspect-state.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, future=True)
    now = datetime.now(timezone.utc)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    Job(
                        kind="materialize_release",
                        status="queued",
                        payload_json=json.dumps({"release_id": 99}),
                        note="queued release",
                        created_at=now - timedelta(minutes=45),
                    ),
                    Job(
                        kind="materialize_release",
                        status="running",
                        payload_json=json.dumps({"release_id": 100}),
                        release_id=100,
                        note="healthy running",
                        created_at=now - timedelta(minutes=31),
                        started_at=now - timedelta(minutes=30),
                        heartbeat_at=now - timedelta(minutes=1),
                        lease_expires_at=now + timedelta(minutes=4),
                        attempt_count=1,
                    ),
                    Job(
                        kind="materialize_release",
                        status="running",
                        payload_json=json.dumps({"release_id": 101}),
                        release_id=101,
                        note="stale running",
                        log="reclaimed stale lease at 2026-04-05T08:00:00Z\n",
                        created_at=now - timedelta(hours=2, minutes=5),
                        started_at=now - timedelta(hours=2),
                        heartbeat_at=now - timedelta(hours=1),
                        lease_expires_at=now - timedelta(minutes=10),
                        attempt_count=2,
                    ),
                    Job(
                        kind="materialize_release",
                        status="completed",
                        payload_json=json.dumps({"release_id": 98}),
                        note="reclaimed once",
                        log="reclaimed stale lease at 2026-04-05T07:00:00Z\ncompleted at 2026-04-05T07:05:00Z\n",
                        created_at=now - timedelta(hours=3),
                        finished_at=now - timedelta(hours=2, minutes=50),
                        attempt_count=2,
                    ),
                ]
            )
            session.commit()
    finally:
        engine.dispose()

    result = _run_cli(
        ["server", "inspect-state", "--database-url", database_url, "--limit", "5", "--json"],
        expect=0,
    )
    payload = _load_json_output(result, label="infinitas server inspect-state")
    assert payload["ok"] is True
    assert payload["jobs"]["counts"]["queued"] == 1
    assert payload["jobs"]["counts"]["running"] == 2
    assert payload["jobs"]["counts"]["stale_running"] == 1
    assert payload["jobs"]["ages"]["longest_running_seconds"] >= 7190
    assert payload["jobs"]["ages"]["oldest_queued_seconds"] >= 2690
    assert payload["jobs"]["recent_stale_running"][0]["release_id"] == 101
    assert payload["jobs"]["recent_reclaimed"][0]["attempt_count"] == 2
