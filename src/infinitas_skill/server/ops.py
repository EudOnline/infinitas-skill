"""Hosted server operations wired into the unified infinitas CLI."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from infinitas_skill.server.backup import run_server_backup, run_server_prune_backups
from infinitas_skill.server.health import run_server_healthcheck
from infinitas_skill.server.repo_checks import require_sqlite_db, sqlite_path_from_url
from infinitas_skill.server.systemd import run_server_render_systemd

SERVER_TOP_LEVEL_HELP = 'Hosted server operations tools'
SERVER_PARSER_DESCRIPTION = 'Hosted server operations CLI'


def server_engine_kwargs(database_url: str) -> dict[str, Any]:
    if database_url.startswith('sqlite:///'):
        return {'connect_args': {'check_same_thread': False}}
    return {}


def isoformat_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace('+00:00', 'Z')


def serialize_job(job: Any) -> dict[str, Any]:
    from server.jobs import load_job_payload

    payload = load_job_payload(job)
    return {
        'id': job.id,
        'kind': job.kind,
        'status': job.status,
        'release_id': job.release_id or payload.get('release_id'),
        'note': job.note or '',
        'error_message': job.error_message or '',
        'created_at': isoformat_or_none(job.created_at),
        'started_at': isoformat_or_none(job.started_at),
        'finished_at': isoformat_or_none(job.finished_at),
    }


def load_latest_review_state_by_exposure(session: Session) -> dict[int, str]:
    from server.modules.review.models import ReviewCase

    latest: dict[int, str] = {}
    rows = session.execute(select(ReviewCase).order_by(ReviewCase.id.asc())).scalars()
    for item in rows:
        latest[item.exposure_id] = item.state or 'none'
    return latest


def build_release_inspection_summary(session: Session) -> dict[str, Any]:
    from server.modules.exposure.models import Exposure

    latest_review_state = load_latest_review_state_by_exposure(session)
    audience_counts: Counter[str] = Counter()
    audience_review_state: defaultdict[str, Counter[str]] = defaultdict(Counter)

    exposures = session.execute(select(Exposure).order_by(Exposure.id.asc())).scalars()
    for exposure in exposures:
        audience = exposure.audience_type or 'unknown'
        review_state = latest_review_state.get(exposure.id, 'none')
        audience_counts[audience] += 1
        audience_review_state[audience][review_state] += 1

    return {
        'by_audience': dict(sorted(audience_counts.items())),
        'by_audience_review_state': {
            audience: dict(sorted(states.items())) for audience, states in sorted(audience_review_state.items())
        },
    }


def build_jobs_inspection_summary(session: Session, *, limit: int) -> dict[str, Any]:
    from server.models import Job

    status_counts = {
        status: count
        for status, count in session.execute(select(Job.status, func.count()).group_by(Job.status)).all()
    }
    warning_count = session.execute(select(func.count()).select_from(Job).where(Job.log.contains('WARNING:'))).scalar_one()

    recent_failed = session.execute(
        select(Job).where(Job.status == 'failed').order_by(Job.id.desc()).limit(limit)
    ).scalars()
    recent_active = session.execute(
        select(Job).where(Job.status.in_(('queued', 'running'))).order_by(Job.id.desc()).limit(limit)
    ).scalars()
    recent_warning = session.execute(
        select(Job).where(Job.log.contains('WARNING:')).order_by(Job.id.desc()).limit(limit)
    ).scalars()

    return {
        'counts': {
            'queued': int(status_counts.get('queued', 0)),
            'running': int(status_counts.get('running', 0)),
            'failed': int(status_counts.get('failed', 0)),
            'completed': int(status_counts.get('completed', 0)),
            'warning': int(warning_count or 0),
        },
        'by_status': dict(sorted((str(key), int(value)) for key, value in status_counts.items())),
        'recent_failed': [serialize_job(item) for item in recent_failed],
        'recent_queued_or_running': [serialize_job(item) for item in recent_active],
        'recent_warning': [serialize_job(item) for item in recent_warning],
    }


def maybe_add_alert(alerts: list[dict[str, Any]], *, kind: str, label: str, actual: int, maximum: int | None):
    if maximum is None:
        return
    if actual <= maximum:
        return
    alerts.append(
        {
            'kind': kind,
            'label': label,
            'actual': actual,
            'max': maximum,
            'message': f'{label} exceeded threshold: {actual} > {maximum}',
        }
    )


def deliver_inspect_webhook(summary: dict[str, Any], url: str):
    from urllib import error, request

    notification = summary['notification']['webhook']
    notification['attempted'] = True
    notification['url'] = url
    payload = json.dumps(summary, ensure_ascii=False).encode('utf-8')
    req = request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with request.urlopen(req, timeout=10) as response:
            notification['status_code'] = response.status
            notification['delivered'] = 200 <= response.status < 300
    except error.HTTPError as exc:
        notification['status_code'] = exc.code
        notification['error'] = f'HTTP {exc.code}'
    except error.URLError as exc:
        notification['error'] = str(exc.reason)
    except Exception as exc:  # pragma: no cover - defensive fallback
        notification['error'] = str(exc)


def write_inspect_fallback(summary: dict[str, Any], path_text: str):
    from pathlib import Path

    notification = summary['notification']['fallback']
    path = Path(path_text)
    notification['attempted'] = True
    notification['path'] = str(path)
    notification['wrote'] = True
    notification['error'] = ''
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except Exception as exc:
        notification['wrote'] = False
        notification['error'] = str(exc)


def build_inspection_summary(
    *,
    database_url: str,
    limit: int,
    max_queued_jobs: int | None = None,
    max_running_jobs: int | None = None,
    max_failed_jobs: int | None = None,
    max_warning_jobs: int | None = None,
    alert_webhook_url: str = '',
    alert_fallback_file: str = '',
) -> dict[str, Any]:
    require_sqlite_db(database_url)
    engine = create_engine(database_url, future=True, **server_engine_kwargs(database_url))
    try:
        with Session(engine) as session:
            jobs = build_jobs_inspection_summary(session, limit=limit)
            releases = build_release_inspection_summary(session)
    finally:
        engine.dispose()

    alerts: list[dict[str, Any]] = []
    maybe_add_alert(alerts, kind='queued_jobs', label='queued jobs', actual=jobs['counts']['queued'], maximum=max_queued_jobs)
    maybe_add_alert(alerts, kind='running_jobs', label='running jobs', actual=jobs['counts']['running'], maximum=max_running_jobs)
    maybe_add_alert(alerts, kind='failed_jobs', label='failed jobs', actual=jobs['counts']['failed'], maximum=max_failed_jobs)
    maybe_add_alert(alerts, kind='warning_jobs', label='warning jobs', actual=jobs['counts']['warning'], maximum=max_warning_jobs)

    summary = {
        'ok': not alerts,
        'database': {
            'kind': 'sqlite',
            'path': str(sqlite_path_from_url(database_url)),
        },
        'jobs': jobs,
        'releases': releases,
        'alerts': alerts,
        'notification': {
            'webhook': {
                'attempted': False,
                'delivered': False,
                'url': alert_webhook_url or '',
                'status_code': None,
                'error': '',
            },
            'fallback': {
                'attempted': False,
                'wrote': False,
                'path': alert_fallback_file or '',
                'error': '',
            },
        },
    }

    if alerts and alert_webhook_url:
        deliver_inspect_webhook(summary, alert_webhook_url)
    if alerts and alert_fallback_file and not summary['notification']['webhook']['delivered']:
        write_inspect_fallback(summary, alert_fallback_file)

    return summary


def emit_inspection_summary(summary: dict[str, Any], as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    counts = summary['jobs']['counts']
    print(f"OK: database {summary['database']['path']}")
    print(
        'OK: jobs '
        f"queued={counts['queued']} running={counts['running']} failed={counts['failed']} warning={counts['warning']}"
    )
    if summary['alerts']:
        for alert in summary['alerts']:
            print(f"ALERT: {alert['message']}")
        return
    print('OK: no inspection thresholds exceeded')


def configure_server_healthcheck_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('--api-url', required=True, help='Hosted registry API base URL or /healthz URL')
    parser.add_argument('--repo-path', required=True, help='Path to the server-owned git checkout')
    parser.add_argument('--artifact-path', required=True, help='Path to the hosted artifact directory')
    parser.add_argument('--database-url', required=True, help='Database URL, currently sqlite:///... only')
    parser.add_argument('--token', default='', help='Reserved for future authenticated probes')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser


def configure_server_backup_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('--repo-path', required=True, help='Path to the server-owned git checkout')
    parser.add_argument('--database-url', required=True, help='Database URL, currently sqlite:///... only')
    parser.add_argument('--artifact-path', required=True, help='Path to the hosted artifact directory')
    parser.add_argument('--output-dir', required=True, help='Directory where backup snapshots should be created')
    parser.add_argument('--label', default='', help='Optional label appended to the backup directory name')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser


def configure_server_render_systemd_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('--output-dir', required=True, help='Directory where rendered files will be written')
    parser.add_argument('--repo-root', required=True, help='Hosted registry repository checkout path')
    parser.add_argument('--python-bin', required=True, help='Python binary used by the hosted services')
    parser.add_argument('--env-file', required=True, help='System path to the deployed environment file')
    parser.add_argument('--service-prefix', default='infinitas-hosted-registry', help='Prefix used for service names')
    parser.add_argument('--service-user', default='infinitas', help='User account that should run the hosted services')
    parser.add_argument('--listen-host', default='127.0.0.1', help='Host binding for the hosted API')
    parser.add_argument('--listen-port', default='8000', help='Port binding for the hosted API')
    parser.add_argument('--worker-poll-interval', type=float, default=5.0, help='Worker poll interval in seconds')
    parser.add_argument('--backup-output-dir', required=True, help='Directory where scheduled backups should be written')
    parser.add_argument('--backup-on-calendar', default='daily', help='systemd OnCalendar expression for backups')
    parser.add_argument('--backup-label', default='scheduled', help='Backup label passed to the backup helper')
    parser.add_argument('--mirror-remote', default='', help='Optional outward mirror remote; when set, render mirror service and timer')
    parser.add_argument('--mirror-branch', default='', help='Optional branch passed to the mirror helper; defaults to current branch when omitted')
    parser.add_argument('--mirror-on-calendar', default='daily', help='systemd OnCalendar expression for optional outward mirroring')
    parser.add_argument('--prune-on-calendar', default='daily', help='systemd OnCalendar expression for backup retention pruning')
    parser.add_argument('--prune-keep-last', type=int, default=7, help='How many newest backup directories the prune job should keep')
    parser.add_argument('--inspect-on-calendar', default='hourly', help='systemd OnCalendar expression for queue inspection runs')
    parser.add_argument('--inspect-limit', type=int, default=10, help='Number of recent rows included in each inspection run')
    parser.add_argument('--inspect-max-queued-jobs', type=int, default=None, help='Alert when queued job count exceeds this threshold')
    parser.add_argument('--inspect-max-running-jobs', type=int, default=None, help='Alert when running job count exceeds this threshold')
    parser.add_argument('--inspect-max-failed-jobs', type=int, default=0, help='Alert when failed job count exceeds this threshold')
    parser.add_argument('--inspect-max-warning-jobs', type=int, default=None, help='Alert when jobs with WARNING log entries exceed this threshold')
    parser.add_argument('--inspect-alert-webhook-url', default='', help='Optional webhook URL for scheduled inspect alert delivery')
    parser.add_argument('--inspect-alert-fallback-file', default='', help='Optional file path for storing the latest inspect alert snapshot when webhook delivery is unavailable')
    parser.add_argument('--artifact-path', default='', help='Override artifact path for the env template and backup service')
    parser.add_argument('--database-url', default='', help='Override database URL for the env template and backup service')
    parser.add_argument('--repo-lock-path', default='', help='Override repo lock path for the env template')
    return parser


def configure_server_prune_backups_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('--backup-root', required=True, help='Directory containing hosted backup snapshot directories')
    parser.add_argument('--keep-last', required=True, type=int, help='How many newest recognized backup directories to keep')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser


def configure_server_worker_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('--poll-interval', type=float, default=5.0, help='Seconds to wait between empty queue polls')
    parser.add_argument('--once', action='store_true', help='Drain the queue once and exit')
    parser.add_argument('--limit', type=int, default=None, help='Maximum jobs to process per loop iteration')
    return parser


def configure_server_inspect_state_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('--database-url', required=True, help='Database URL, currently sqlite:///... only')
    parser.add_argument('--limit', type=int, default=10, help='Number of recent jobs to include in detail lists')
    parser.add_argument('--max-queued-jobs', type=int, default=None, help='Alert when queued job count exceeds this threshold')
    parser.add_argument('--max-running-jobs', type=int, default=None, help='Alert when running job count exceeds this threshold')
    parser.add_argument('--max-failed-jobs', type=int, default=None, help='Alert when failed job count exceeds this threshold')
    parser.add_argument('--max-warning-jobs', type=int, default=None, help='Alert when jobs with WARNING log entries exceed this threshold')
    parser.add_argument('--alert-webhook-url', default='', help='Optional webhook URL for alert summary delivery')
    parser.add_argument('--alert-fallback-file', default='', help='Optional file path for storing the latest alert summary JSON')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser


def build_server_healthcheck_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Hosted registry server health check', prog=prog)
    return configure_server_healthcheck_parser(parser)


def build_server_backup_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Create a hosted registry backup set', prog=prog)
    return configure_server_backup_parser(parser)


def build_server_render_systemd_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Render a hosted registry systemd deployment bundle', prog=prog)
    return configure_server_render_systemd_parser(parser)


def build_server_prune_backups_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Prune older hosted registry backup snapshots', prog=prog)
    return configure_server_prune_backups_parser(parser)


def build_server_worker_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run the hosted registry worker loop', prog=prog)
    return configure_server_worker_parser(parser)


def build_server_inspect_state_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Inspect hosted registry queue and release state', prog=prog)
    return configure_server_inspect_state_parser(parser)


def run_server_worker(*, poll_interval: float = 5.0, once: bool = False, limit: int | None = None) -> int:
    from server.db import ensure_database_ready
    from server.worker import run_worker_loop

    ensure_database_ready()
    if once:
        processed = run_worker_loop(limit=limit)
        print(f'processed {processed} job(s) in once mode')
        return 0

    try:
        while True:
            processed = run_worker_loop(limit=limit)
            print(f'processed {processed} job(s)')
            if processed == 0:
                time.sleep(max(poll_interval, 0.1))
    except KeyboardInterrupt:
        print('worker loop interrupted; exiting cleanly')
        return 0


def run_server_inspect_state(
    *,
    database_url: str,
    limit: int,
    max_queued_jobs: int | None = None,
    max_running_jobs: int | None = None,
    max_failed_jobs: int | None = None,
    max_warning_jobs: int | None = None,
    alert_webhook_url: str = '',
    alert_fallback_file: str = '',
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
    return 2 if summary['alerts'] else 0


def configure_server_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(
        dest='server_command',
        metavar='{healthcheck,backup,render-systemd,prune-backups,worker,inspect-state}',
    )

    healthcheck = subparsers.add_parser(
        'healthcheck',
        help='Run hosted server health checks',
        description='Run hosted server health checks',
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
        'backup',
        help='Create a hosted registry backup set',
        description='Create a hosted registry backup set',
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
        'render-systemd',
        help='Render a hosted registry systemd deployment bundle',
        description='Render a hosted registry systemd deployment bundle',
    )
    configure_server_render_systemd_parser(render_systemd)
    render_systemd.set_defaults(_handler=run_server_render_systemd)

    prune_backups = subparsers.add_parser(
        'prune-backups',
        help='Prune older hosted registry backup snapshots',
        description='Prune older hosted registry backup snapshots',
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
        'worker',
        help='Run the hosted registry worker loop',
        description='Run the hosted registry worker loop',
    )
    configure_server_worker_parser(worker)
    worker.set_defaults(
        _handler=lambda args: run_server_worker(
            poll_interval=args.poll_interval,
            once=args.once,
            limit=args.limit,
        )
    )

    inspect_state = subparsers.add_parser(
        'inspect-state',
        help='Inspect hosted registry queue and release state',
        description='Inspect hosted registry queue and release state',
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
    return parser


def build_server_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=SERVER_PARSER_DESCRIPTION, prog=prog)
    return configure_server_parser(parser)


def server_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = build_server_parser(prog=prog)
    args = parser.parse_args(argv)
    handler = getattr(args, '_handler', None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


__all__ = [
    'SERVER_PARSER_DESCRIPTION',
    'SERVER_TOP_LEVEL_HELP',
    'build_server_backup_parser',
    'build_server_healthcheck_parser',
    'build_server_inspect_state_parser',
    'build_server_parser',
    'build_server_prune_backups_parser',
    'build_server_render_systemd_parser',
    'build_server_worker_parser',
    'configure_server_backup_parser',
    'configure_server_healthcheck_parser',
    'configure_server_inspect_state_parser',
    'configure_server_parser',
    'configure_server_prune_backups_parser',
    'configure_server_render_systemd_parser',
    'configure_server_worker_parser',
    'run_server_backup',
    'run_server_healthcheck',
    'run_server_inspect_state',
    'run_server_prune_backups',
    'run_server_render_systemd',
    'run_server_worker',
    'server_main',
]
