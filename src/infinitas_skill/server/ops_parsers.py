"""Argument parser builders for hosted server operations."""

from __future__ import annotations

import argparse


def configure_server_healthcheck_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--api-url", required=True, help="Hosted registry API base URL or /healthz URL"
    )
    parser.add_argument("--repo-path", required=True, help="Path to the server-owned git checkout")
    parser.add_argument(
        "--artifact-path", required=True, help="Path to the hosted artifact directory"
    )
    parser.add_argument(
        "--database-url", required=True, help="Database URL, currently sqlite:///... only"
    )
    parser.add_argument("--token", default="", help="Reserved for future authenticated probes")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    return parser


def configure_server_backup_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--repo-path", required=True, help="Path to the server-owned git checkout")
    parser.add_argument(
        "--database-url", required=True, help="Database URL, currently sqlite:///... only"
    )
    parser.add_argument(
        "--artifact-path", required=True, help="Path to the hosted artifact directory"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Directory where backup snapshots should be created"
    )
    parser.add_argument(
        "--label", default="", help="Optional label appended to the backup directory name"
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    return parser


def configure_server_render_systemd_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "--output-dir", required=True, help="Directory where rendered files will be written"
    )
    parser.add_argument(
        "--repo-root", required=True, help="Hosted registry repository checkout path"
    )
    parser.add_argument(
        "--python-bin", required=True, help="Python binary used by the hosted services"
    )
    parser.add_argument(
        "--env-file", required=True, help="System path to the deployed environment file"
    )
    parser.add_argument(
        "--service-prefix",
        default="infinitas-hosted-registry",
        help="Prefix used for service names",
    )
    parser.add_argument(
        "--service-user",
        default="infinitas",
        help="User account that should run the hosted services",
    )
    parser.add_argument(
        "--listen-host", default="127.0.0.1", help="Host binding for the hosted API"
    )
    parser.add_argument("--listen-port", default="8000", help="Port binding for the hosted API")
    parser.add_argument(
        "--worker-poll-interval", type=float, default=5.0, help="Worker poll interval in seconds"
    )
    parser.add_argument(
        "--backup-output-dir",
        required=True,
        help="Directory where scheduled backups should be written",
    )
    parser.add_argument(
        "--backup-on-calendar", default="daily", help="systemd OnCalendar expression for backups"
    )
    parser.add_argument(
        "--backup-label", default="scheduled", help="Backup label passed to the backup helper"
    )
    parser.add_argument(
        "--mirror-remote",
        default="",
        help="Optional outward mirror remote; when set, render mirror service and timer",
    )
    parser.add_argument(
        "--mirror-branch",
        default="",
        help="Optional branch passed to the mirror helper; defaults to current branch when omitted",
    )
    parser.add_argument(
        "--mirror-on-calendar",
        default="daily",
        help="systemd OnCalendar expression for optional outward mirroring",
    )
    parser.add_argument(
        "--prune-on-calendar",
        default="daily",
        help="systemd OnCalendar expression for backup retention pruning",
    )
    parser.add_argument(
        "--prune-keep-last",
        type=int,
        default=7,
        help="How many newest backup directories the prune job should keep",
    )
    parser.add_argument(
        "--inspect-on-calendar",
        default="hourly",
        help="systemd OnCalendar expression for queue inspection runs",
    )
    parser.add_argument(
        "--inspect-limit",
        type=int,
        default=10,
        help="Number of recent rows included in each inspection run",
    )
    parser.add_argument(
        "--inspect-max-queued-jobs",
        type=int,
        default=None,
        help="Alert when queued job count exceeds this threshold",
    )
    parser.add_argument(
        "--inspect-max-running-jobs",
        type=int,
        default=None,
        help="Alert when running job count exceeds this threshold",
    )
    parser.add_argument(
        "--inspect-max-failed-jobs",
        type=int,
        default=0,
        help="Alert when failed job count exceeds this threshold",
    )
    parser.add_argument(
        "--inspect-max-warning-jobs",
        type=int,
        default=None,
        help="Alert when jobs with WARNING log entries exceed this threshold",
    )
    parser.add_argument(
        "--inspect-alert-webhook-url",
        default="",
        help="Optional webhook URL for scheduled inspect alert delivery",
    )
    parser.add_argument(
        "--inspect-alert-fallback-file",
        default="",
        help=(
            "Optional file path for storing the latest inspect alert snapshot "
            "when webhook delivery is unavailable"
        ),
    )
    parser.add_argument(
        "--artifact-path",
        default="",
        help="Override artifact path for the env template and backup service",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Override database URL for the env template and backup service",
    )
    parser.add_argument(
        "--repo-lock-path", default="", help="Override repo lock path for the env template"
    )
    return parser


def configure_server_prune_backups_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "--backup-root",
        required=True,
        help="Directory containing hosted backup snapshot directories",
    )
    parser.add_argument(
        "--keep-last",
        required=True,
        type=int,
        help="How many newest recognized backup directories to keep",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    return parser


def configure_server_worker_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--poll-interval", type=float, default=5.0, help="Seconds to wait between empty queue polls"
    )
    parser.add_argument("--once", action="store_true", help="Drain the queue once and exit")
    parser.add_argument(
        "--limit", type=int, default=None, help="Maximum jobs to process per loop iteration"
    )
    return parser


def configure_server_inspect_state_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "--database-url", required=True, help="Database URL, currently sqlite:///... only"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Number of recent jobs to include in detail lists"
    )
    parser.add_argument(
        "--max-queued-jobs",
        type=int,
        default=None,
        help="Alert when queued job count exceeds this threshold",
    )
    parser.add_argument(
        "--max-running-jobs",
        type=int,
        default=None,
        help="Alert when running job count exceeds this threshold",
    )
    parser.add_argument(
        "--max-failed-jobs",
        type=int,
        default=None,
        help="Alert when failed job count exceeds this threshold",
    )
    parser.add_argument(
        "--max-warning-jobs",
        type=int,
        default=None,
        help="Alert when jobs with WARNING log entries exceed this threshold",
    )
    parser.add_argument(
        "--alert-webhook-url", default="", help="Optional webhook URL for alert summary delivery"
    )
    parser.add_argument(
        "--alert-fallback-file",
        default="",
        help="Optional file path for storing the latest alert summary JSON",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    return parser


def build_server_healthcheck_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hosted registry server health check", prog=prog)
    return configure_server_healthcheck_parser(parser)


def build_server_backup_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a hosted registry backup set", prog=prog)
    return configure_server_backup_parser(parser)


def build_server_render_systemd_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a hosted registry systemd deployment bundle", prog=prog
    )
    return configure_server_render_systemd_parser(parser)


def build_server_prune_backups_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prune older hosted registry backup snapshots", prog=prog
    )
    return configure_server_prune_backups_parser(parser)


def build_server_worker_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the hosted registry worker loop", prog=prog)
    return configure_server_worker_parser(parser)


def build_server_inspect_state_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect hosted registry queue and release state", prog=prog
    )
    return configure_server_inspect_state_parser(parser)


__all__ = [
    "build_server_backup_parser",
    "build_server_healthcheck_parser",
    "build_server_inspect_state_parser",
    "build_server_prune_backups_parser",
    "build_server_render_systemd_parser",
    "build_server_worker_parser",
    "configure_server_backup_parser",
    "configure_server_healthcheck_parser",
    "configure_server_inspect_state_parser",
    "configure_server_prune_backups_parser",
    "configure_server_render_systemd_parser",
    "configure_server_worker_parser",
]
