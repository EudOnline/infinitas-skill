"""Hosted server operations wired into the unified infinitas CLI."""

from __future__ import annotations

import argparse
import json
import time
from contextlib import nullcontext
from typing import Any

from infinitas_skill.server.backup import run_server_backup, run_server_prune_backups
from infinitas_skill.server.db_utils import standalone_session
from infinitas_skill.server.health import run_server_healthcheck
from infinitas_skill.server.inspection_notifications import (
    deliver_inspect_webhook,
    write_inspect_fallback,
)
from infinitas_skill.server.inspection_summary import (
    build_jobs_inspection_summary,
    build_release_inspection_summary,
    maybe_add_alert,
)
from infinitas_skill.server.ops_parsers import (
    build_server_backup_parser,
    build_server_healthcheck_parser,
    build_server_inspect_state_parser,
    build_server_prune_backups_parser,
    build_server_render_systemd_parser,
    build_server_worker_healthcheck_parser,
    build_server_worker_parser,
    configure_server_backup_parser,
    configure_server_healthcheck_parser,
    configure_server_inspect_state_parser,
    configure_server_prune_backups_parser,
    configure_server_render_systemd_parser,
    configure_server_worker_healthcheck_parser,
    configure_server_worker_parser,
)
from infinitas_skill.server.repo_checks import require_sqlite_db, sqlite_path_from_url
from infinitas_skill.server.restore import run_server_restore_rehearsal
from infinitas_skill.server.systemd import run_server_render_systemd
from infinitas_skill.server.worker_health import (
    maintain_worker_heartbeat,
    run_worker_healthcheck,
)

SERVER_TOP_LEVEL_HELP = "Hosted server operations tools"
SERVER_PARSER_DESCRIPTION = "Hosted server operations CLI"


def build_inspection_summary(
    *,
    database_url: str,
    limit: int,
    max_queued_jobs: int | None = None,
    max_running_jobs: int | None = None,
    max_failed_jobs: int | None = None,
    max_warning_jobs: int | None = None,
    alert_webhook_url: str = "",
    alert_fallback_file: str = "",
) -> dict[str, Any]:
    require_sqlite_db(database_url)
    with standalone_session(database_url) as session:
        jobs = build_jobs_inspection_summary(session, limit=limit)
        releases = build_release_inspection_summary(session)

    alerts: list[dict[str, Any]] = []
    maybe_add_alert(
        alerts,
        kind="queued_jobs",
        label="queued jobs",
        actual=jobs["counts"]["queued"],
        maximum=max_queued_jobs,
    )
    maybe_add_alert(
        alerts,
        kind="running_jobs",
        label="running jobs",
        actual=jobs["counts"]["running"],
        maximum=max_running_jobs,
    )
    maybe_add_alert(
        alerts,
        kind="failed_jobs",
        label="failed jobs",
        actual=jobs["counts"]["failed"],
        maximum=max_failed_jobs,
    )
    maybe_add_alert(
        alerts,
        kind="warning_jobs",
        label="warning jobs",
        actual=jobs["counts"]["warning"],
        maximum=max_warning_jobs,
    )

    summary: dict[str, Any] = {
        "ok": not alerts,
        "database": {
            "kind": "sqlite",
            "path": str(sqlite_path_from_url(database_url)),
        },
        "jobs": jobs,
        "releases": releases,
        "alerts": alerts,
        "notification": {
            "webhook": {
                "attempted": False,
                "delivered": False,
                "url": alert_webhook_url or "",
                "status_code": None,
                "error": "",
            },
            "fallback": {
                "attempted": False,
                "wrote": False,
                "path": alert_fallback_file or "",
                "error": "",
            },
        },
    }

    if alerts and alert_webhook_url:
        deliver_inspect_webhook(summary, alert_webhook_url)
    if alerts and alert_fallback_file and not summary["notification"]["webhook"]["delivered"]:
        write_inspect_fallback(summary, alert_fallback_file)

    return summary


def emit_inspection_summary(summary: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    counts = summary["jobs"]["counts"]
    ages = summary["jobs"].get("ages") or {}
    print(f"OK: database {summary['database']['path']}")
    print(
        "OK: jobs "
        f"queued={counts['queued']} running={counts['running']} stale_running={counts.get('stale_running', 0)} "
        f"failed={counts['failed']} warning={counts['warning']}"
    )
    print(
        "OK: queue health "
        f"oldest_queued_seconds={ages.get('oldest_queued_seconds')} "
        f"longest_running_seconds={ages.get('longest_running_seconds')}"
    )
    if summary["alerts"]:
        for alert in summary["alerts"]:
            print(f"ALERT: {alert['message']}")
        return
    print("OK: no inspection thresholds exceeded")


def run_server_worker(
    *,
    poll_interval: float = 5.0,
    once: bool = False,
    limit: int | None = None,
    health_path: str = "",
) -> int:
    from server.lifecycle import ensure_database_ready
    from server.worker import run_worker_loop

    ensure_database_ready()
    heartbeat = maintain_worker_heartbeat(
        health_path,
        interval_seconds=min(max(poll_interval, 0.1), 10.0),
    )
    with heartbeat if health_path else nullcontext():
        if once:
            processed = run_worker_loop(limit=limit)
            print(f"processed {processed} job(s) in once mode")
            return 0

        try:
            while True:
                processed = run_worker_loop(limit=limit)
                print(f"processed {processed} job(s)")
                if processed == 0:
                    time.sleep(max(poll_interval, 0.1))
        except KeyboardInterrupt:
            print("worker loop interrupted; exiting cleanly")
            return 0


def run_server_inspect_state(
    *,
    database_url: str,
    limit: int,
    max_queued_jobs: int | None = None,
    max_running_jobs: int | None = None,
    max_failed_jobs: int | None = None,
    max_warning_jobs: int | None = None,
    alert_webhook_url: str = "",
    alert_fallback_file: str = "",
    as_json: bool = False,
) -> int:
    summary = build_inspection_summary(
        database_url=database_url,
        limit=limit,
        max_queued_jobs=max_queued_jobs,
        max_running_jobs=max_running_jobs,
        max_failed_jobs=max_failed_jobs,
        max_warning_jobs=max_warning_jobs,
        alert_webhook_url=alert_webhook_url,
        alert_fallback_file=alert_fallback_file,
    )
    emit_inspection_summary(summary, as_json=as_json)
    return 2 if summary["alerts"] else 0


def _configure_server_core_commands(subparsers: argparse._SubParsersAction) -> None:
    healthcheck = subparsers.add_parser(
        "healthcheck",
        help="Run hosted server health checks",
        description="Run hosted server health checks",
    )
    configure_server_healthcheck_parser(healthcheck)
    healthcheck.set_defaults(
        _handler=lambda args: run_server_healthcheck(
            api_url=args.api_url,
            repo_path=args.repo_path,
            artifact_path=args.artifact_path,
            database_url=args.database_url,
            token=args.token,
            as_json=args.json,
        )
    )

    backup = subparsers.add_parser(
        "backup",
        help="Create a hosted registry backup set",
        description="Create a hosted registry backup set",
    )
    configure_server_backup_parser(backup)
    backup.set_defaults(
        _handler=lambda args: run_server_backup(
            repo_path=args.repo_path,
            database_url=args.database_url,
            artifact_path=args.artifact_path,
            output_dir=args.output_dir,
            label=args.label,
            as_json=args.json,
        )
    )

    render_systemd = subparsers.add_parser(
        "render-systemd",
        help="Render a hosted registry systemd deployment bundle",
        description="Render a hosted registry systemd deployment bundle",
    )
    configure_server_render_systemd_parser(render_systemd)
    render_systemd.set_defaults(_handler=run_server_render_systemd)


def _configure_server_runtime_commands(subparsers: argparse._SubParsersAction) -> None:
    prune_backups = subparsers.add_parser(
        "prune-backups",
        help="Prune older hosted registry backup snapshots",
        description="Prune older hosted registry backup snapshots",
    )
    configure_server_prune_backups_parser(prune_backups)
    prune_backups.set_defaults(
        _handler=lambda args: run_server_prune_backups(
            backup_root=args.backup_root,
            keep_last=args.keep_last,
            as_json=args.json,
        )
    )

    worker = subparsers.add_parser(
        "worker",
        help="Run the hosted registry worker loop",
        description="Run the hosted registry worker loop",
    )
    configure_server_worker_parser(worker)
    worker.set_defaults(
        _handler=lambda args: run_server_worker(
            poll_interval=args.poll_interval,
            once=args.once,
            limit=args.limit,
            health_path=args.health_path,
        )
    )

    worker_healthcheck = subparsers.add_parser(
        "worker-healthcheck",
        help="Check the hosted worker heartbeat",
        description="Check the hosted worker heartbeat",
    )
    configure_server_worker_healthcheck_parser(worker_healthcheck)
    worker_healthcheck.set_defaults(
        _handler=lambda args: run_worker_healthcheck(
            health_path=args.health_path,
            max_age_seconds=args.max_age_seconds,
            as_json=args.json,
        )
    )

    inspect_state = subparsers.add_parser(
        "inspect-state",
        help="Inspect hosted registry queue and release state",
        description="Inspect hosted registry queue and release state",
    )
    configure_server_inspect_state_parser(inspect_state)
    inspect_state.set_defaults(
        _handler=lambda args: run_server_inspect_state(
            database_url=args.database_url,
            limit=args.limit,
            max_queued_jobs=args.max_queued_jobs,
            max_running_jobs=args.max_running_jobs,
            max_failed_jobs=args.max_failed_jobs,
            max_warning_jobs=args.max_warning_jobs,
            alert_webhook_url=args.alert_webhook_url,
            alert_fallback_file=args.alert_fallback_file,
            as_json=args.json,
        )
    )

    restore = subparsers.add_parser(
        "restore-rehearsal",
        help="Rehearse restoring a hosted registry backup",
    )
    restore.add_argument("--backup-dir", required=True)
    restore.add_argument("--output-dir", required=True)
    restore.add_argument("--json", action="store_true")
    restore.set_defaults(
        _handler=lambda args: run_server_restore_rehearsal(
            backup_dir=args.backup_dir,
            output_dir=args.output_dir,
            as_json=args.json,
        )
    )


def configure_server_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(
        dest="server_command",
        metavar=(
            "{healthcheck,backup,render-systemd,prune-backups,worker,"
            "worker-healthcheck,inspect-state}"
        ),
    )
    _configure_server_core_commands(subparsers)
    _configure_server_runtime_commands(subparsers)
    return parser


def build_server_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=SERVER_PARSER_DESCRIPTION, prog=prog)
    return configure_server_parser(parser)


def server_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = build_server_parser(prog=prog)
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return int(handler(args))


__all__ = [
    "SERVER_PARSER_DESCRIPTION",
    "SERVER_TOP_LEVEL_HELP",
    "build_server_backup_parser",
    "build_server_healthcheck_parser",
    "build_server_inspect_state_parser",
    "build_server_parser",
    "build_server_prune_backups_parser",
    "build_server_render_systemd_parser",
    "build_server_worker_healthcheck_parser",
    "build_server_worker_parser",
    "configure_server_backup_parser",
    "configure_server_healthcheck_parser",
    "configure_server_inspect_state_parser",
    "configure_server_parser",
    "configure_server_prune_backups_parser",
    "configure_server_render_systemd_parser",
    "configure_server_worker_healthcheck_parser",
    "configure_server_worker_parser",
    "run_server_backup",
    "run_server_healthcheck",
    "run_server_inspect_state",
    "run_server_prune_backups",
    "run_server_render_systemd",
    "run_server_worker",
    "server_main",
]
