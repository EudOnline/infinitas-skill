from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from test_support.server_ops import HealthServer
from test_support.server_ops import run_command as shared_run_command

from server.models import AuditEvent, Base
from tests.fixtures.repo_state import create_repo_state

ROOT = Path(__file__).resolve().parents[2]


def _run(command: list[str], *, cwd: Path = ROOT, expect: int | None = 0, env: dict[str, str] | None = None):
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
        f"{ROOT / 'src'}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(ROOT / "src")
    )
    return _run([sys.executable, "-m", "infinitas_skill.cli.main", *args], expect=expect, env=merged_env)


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
        "memory-health",
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
        assert cli_payload.get("api", {}).get("url", "").endswith("/healthz")
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


def test_server_memory_health_command_returns_status_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "memory-health.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, future=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:1",
                        event_type="memory.writeback.failed",
                        actor_ref="principal:1",
                        payload_json=json.dumps(
                            {
                                "status": "failed",
                                "backend": "memo0",
                                "lifecycle_event": "task.review.approve",
                            }
                        ),
                    ),
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:2",
                        event_type="memory.writeback.stored",
                        actor_ref="principal:1",
                        payload_json=json.dumps(
                            {
                                "status": "stored",
                                "backend": "memo0",
                                "lifecycle_event": "task.release.ready",
                            }
                        ),
                    ),
                ]
            )
            session.commit()
    finally:
        engine.dispose()

    result = _run_cli(
        ["server", "memory-health", "--database-url", database_url, "--json"],
        expect=0,
    )
    payload = _load_json_output(result, label="infinitas server memory-health")
    assert payload["ok"] is True
    assert payload["writeback_status_counts"]["failed"] == 1
    assert payload["writeback_status_counts"]["stored"] == 1
    assert payload["backend_names"] == ["memo0"]


def test_server_memory_curation_command_returns_candidate_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "memory-curation.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, future=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:1",
                        event_type="memory.writeback.stored",
                        actor_ref="principal:1",
                        occurred_at=datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                            {
                                "status": "stored",
                                "backend": "memo0",
                                "lifecycle_event": "task.review.approve",
                                "payload": {"qualified_name": "team/demo", "decision": "approve"},
                            }
                        ),
                    ),
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:2",
                        event_type="memory.writeback.stored",
                        actor_ref="principal:1",
                        occurred_at=datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                            {
                                "status": "stored",
                                "backend": "memo0",
                                "lifecycle_event": "task.review.approve",
                                "payload": {"qualified_name": "team/demo", "decision": "approve"},
                            }
                        ),
                    ),
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:3",
                        event_type="memory.writeback.stored",
                        actor_ref="principal:1",
                        occurred_at=datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                            {
                                "status": "stored",
                                "backend": "memo0",
                                "lifecycle_event": "task.authoring.create_draft",
                                "payload": {"qualified_name": "team/demo", "state": "draft"},
                            }
                        ),
                    ),
                ]
            )
            session.commit()
    finally:
        engine.dispose()

    result = _run_cli(
        ["server", "memory-curation", "--database-url", database_url, "--json"],
        expect=0,
    )
    payload = _load_json_output(result, label="infinitas server memory-curation")
    assert payload["ok"] is True
    assert payload["action"] == "plan"
    assert payload["candidate_counts"]["duplicate_groups"] == 1
    assert payload["candidate_counts"]["expired_by_policy"] == 1


def test_server_memory_curation_command_accepts_execution_flags(tmp_path: Path) -> None:
    db_path = tmp_path / "memory-curation-flags.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, future=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                AuditEvent(
                    aggregate_type="memory_writeback",
                    aggregate_id="mw:1",
                    event_type="memory.writeback.stored",
                    actor_ref="principal:1",
                    occurred_at=datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
                    payload_json=json.dumps(
                        {
                            "status": "stored",
                            "backend": "memo0",
                            "memory_id": "memory-1",
                            "lifecycle_event": "task.authoring.create_draft",
                            "payload": {"qualified_name": "team/demo", "state": "draft"},
                        }
                    ),
                )
            )
            session.commit()
    finally:
        engine.dispose()

    result = _run_cli(
        [
            "server",
            "memory-curation",
            "--database-url",
            database_url,
            "--action",
            "prune",
            "--max-actions",
            "1",
            "--json",
        ],
        expect=0,
    )
    payload = _load_json_output(result, label="infinitas server memory-curation flags")
    assert payload["action"] == "prune"
    assert payload["apply"] is False
    assert payload["execution"]["selected_candidates"] == 1


def main() -> None:
    assert_server_cli_help_lists_maintained_subcommands()
    assert_server_ops_split_into_modules()
    assert_server_healthcheck_reports_expected_summary()
