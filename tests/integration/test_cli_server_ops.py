from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_support.server_ops import HealthServer
from test_support.server_ops import run_command as shared_run_command

from server.models import AuditEvent, Base, Job
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
        "memory-curation",
        "memory-observability",
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


def test_server_memory_observability_command_summarizes_memory_ops(tmp_path: Path) -> None:
    db_path = tmp_path / "memory-observability.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, future=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:0",
                        event_type="memory.writeback.failed",
                        actor_ref="principal:0",
                        occurred_at=datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc),
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
                        aggregate_id="mw:1",
                        event_type="memory.writeback.stored",
                        actor_ref="principal:1",
                        occurred_at=datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                            {
                                "status": "stored",
                                "backend": "memo0",
                                "lifecycle_event": "task.release.ready",
                            }
                        ),
                    ),
                    AuditEvent(
                        aggregate_type="memory_curation",
                        aggregate_id="memory_writeback:0",
                        event_type="memory.curation.failed",
                        actor_ref="system:memory-curation",
                        occurred_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive", "status": "failed"}),
                    ),
                    AuditEvent(
                        aggregate_type="memory_curation",
                        aggregate_id="memory_writeback:1",
                        event_type="memory.curation.archived",
                        actor_ref="system:memory-curation",
                        occurred_at=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive", "status": "archived"}),
                    ),
                    Job(
                        kind="memory_curation",
                        status="failed",
                        created_at=datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive", "apply": True}),
                        note="failed archive",
                    ),
                    Job(
                        kind="memory_curation",
                        status="completed",
                        created_at=datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive", "apply": True}),
                        note="completed archive",
                    ),
                    AuditEvent(
                        aggregate_type="memory_retrieval",
                        aggregate_id="mr:0",
                        event_type="memory.retrieval.inspect",
                        actor_ref="system:discovery:inspect-script",
                        occurred_at=datetime(2026, 4, 2, 11, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                                {
                                    "operation": "inspect",
                                    "memory": {"status": "error", "used": False, "matched_count": 0},
                                    "effect": "error",
                                }
                            ),
                        ),
                    AuditEvent(
                        aggregate_type="memory_retrieval",
                        aggregate_id="mr:1",
                        event_type="memory.retrieval.recommend",
                        actor_ref="system:discovery:recommend-script",
                        occurred_at=datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                                {
                                    "operation": "recommend",
                                    "memory": {"status": "matched", "used": True, "matched_count": 2},
                                    "effect": "helpful",
                                }
                            ),
                        ),
                ]
            )
            session.commit()
    finally:
        engine.dispose()

    result = _run_cli(
        [
            "server",
            "memory-observability",
            "--database-url",
            database_url,
            "--window-hours",
            "24",
            "--now",
            "2026-04-03T12:00:00Z",
            "--json",
        ],
        expect=0,
    )
    payload = _load_json_output(result, label="infinitas server memory-observability")
    assert payload["ok"] is True
    assert payload["writeback"]["writeback_status_counts"]["stored"] == 1
    assert payload["writeback"]["writeback_status_counts"]["failed"] == 1
    assert payload["curation"]["status_counts"]["archived"] == 1
    assert payload["curation"]["status_counts"]["failed"] == 1
    assert payload["jobs"]["status_counts"]["completed"] == 1
    assert payload["jobs"]["status_counts"]["failed"] == 1
    assert payload["retrieval"]["status_counts"]["matched"] == 1
    assert payload["retrieval"]["status_counts"]["error"] == 1
    assert payload["retrieval"]["effect_counts"]["helpful"] == 1
    assert payload["retrieval"]["operation_counts"]["recommend"] == 1
    assert payload["baselines"]["window_hours"] == 24
    assert payload["baselines"]["writeback"]["delta"]["stored_rate"] == 1.0
    assert payload["baselines"]["curation"]["delta"]["archived_rate"] == 1.0
    assert payload["baselines"]["jobs"]["delta"]["completed_rate"] == 1.0
    assert payload["baselines"]["retrieval"]["delta"]["matched_rate"] == 1.0
    assert payload["baselines"]["retrieval"]["delta"]["helpful_rate"] == 1.0


def test_server_memory_baselines_command_returns_windowed_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "memory-baselines.db"
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
                        occurred_at=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                            {"status": "stored", "backend": "memo0", "lifecycle_event": "task.release.ready"}
                        ),
                    ),
                    AuditEvent(
                        aggregate_type="memory_curation",
                        aggregate_id="memory_writeback:1",
                        event_type="memory.curation.archived",
                        actor_ref="system:memory-curation",
                        occurred_at=datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive", "status": "archived"}),
                    ),
                    Job(
                        kind="memory_curation",
                        status="completed",
                        created_at=datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive"}),
                        note="completed archive",
                    ),
                    AuditEvent(
                        aggregate_type="memory_retrieval",
                        aggregate_id="mr:1",
                        event_type="memory.retrieval.recommend",
                        actor_ref="system:discovery:recommend-script",
                        occurred_at=datetime(2026, 4, 3, 7, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                                {
                                    "operation": "recommend",
                                    "memory": {"status": "matched", "used": True, "matched_count": 2},
                                    "effect": "helpful",
                                }
                            ),
                        ),
                ]
            )
            session.commit()
    finally:
        engine.dispose()

    result = _run_cli(
        [
            "server",
            "memory-baselines",
            "--database-url",
            database_url,
            "--window-hours",
            "24",
            "--now",
            "2026-04-03T12:00:00Z",
            "--json",
        ],
        expect=0,
    )
    payload = _load_json_output(result, label="infinitas server memory-baselines")
    assert payload["ok"] is True
    assert payload["window_hours"] == 24
    assert payload["writeback"]["recent"]["totals"]["count"] == 1
    assert payload["curation"]["recent"]["totals"]["count"] == 1
    assert payload["jobs"]["recent"]["totals"]["count"] == 1
    assert payload["retrieval"]["recent"]["totals"]["count"] == 1


def test_server_memory_curation_command_can_enqueue_job(tmp_path: Path) -> None:
    db_path = tmp_path / "memory-curation-queue.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, future=True)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    result = _run_cli(
        [
            "server",
            "memory-curation",
            "--database-url",
            database_url,
            "--action",
            "archive",
            "--apply",
            "--max-actions",
            "3",
            "--enqueue",
            "--json",
        ],
        expect=0,
    )
    payload = _load_json_output(result, label="infinitas server memory-curation enqueue")
    assert payload["ok"] is True
    assert payload["queued"] is True
    assert payload["job"]["kind"] == "memory_curation"
    assert payload["job"]["status"] == "queued"

    engine = create_engine(database_url, future=True)
    try:
        with Session(engine) as session:
            job = session.scalar(select(AuditEvent.id).where(AuditEvent.aggregate_type == "memory_curation"))
            assert job is None
            queued_job = session.execute(select(Job.kind, Job.payload_json).where(Job.kind == "memory_curation")).first()
            assert queued_job is not None
            assert queued_job[0] == "memory_curation"
            assert '"action": "archive"' in queued_job[1]
    finally:
        engine.dispose()


def test_server_memory_curation_command_can_enqueue_using_server_policy(tmp_path: Path) -> None:
    db_path = tmp_path / "memory-curation-policy-queue.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, future=True)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    result = _run_cli(
        [
            "server",
            "memory-curation",
            "--database-url",
            database_url,
            "--use-server-policy",
            "--enqueue",
            "--json",
        ],
        expect=0,
        env={
            "INFINITAS_SERVER_ENV": "test",
            "INFINITAS_SERVER_SECRET_KEY": "test-secret-key",
            "INFINITAS_SERVER_BOOTSTRAP_USERS": "[]",
            "INFINITAS_SERVER_MEMORY_CURATION_ACTION": "prune",
            "INFINITAS_SERVER_MEMORY_CURATION_APPLY": "1",
            "INFINITAS_SERVER_MEMORY_CURATION_LIMIT": "41",
            "INFINITAS_SERVER_MEMORY_CURATION_MAX_ACTIONS": "6",
            "INFINITAS_SERVER_MEMORY_CURATION_ACTOR_REF": "system:scheduled-curation",
        },
    )
    payload = _load_json_output(result, label="infinitas server memory-curation policy enqueue")
    assert payload["ok"] is True
    assert payload["queued"] is True
    assert payload["job"]["payload"]["action"] == "prune"
    assert payload["job"]["payload"]["apply"] is True
    assert payload["job"]["payload"]["limit"] == 41
    assert payload["job"]["payload"]["max_actions"] == 6
    assert payload["job"]["payload"]["actor_ref"] == "system:scheduled-curation"


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
                        kind="memory_curation",
                        status="queued",
                        payload_json=json.dumps({"action": "archive"}),
                        note="queued archive",
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
                        kind="memory_curation",
                        status="completed",
                        payload_json=json.dumps({"action": "archive"}),
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


def main() -> None:
    assert_server_cli_help_lists_maintained_subcommands()
    assert_server_ops_split_into_modules()
    assert_server_healthcheck_reports_expected_summary()
