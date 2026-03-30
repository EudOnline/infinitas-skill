"""Hosted server operations wired into the unified infinitas CLI."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

SERVER_TOP_LEVEL_HELP = 'Hosted server operations tools'
SERVER_PARSER_DESCRIPTION = 'Hosted server operations CLI'
BACKUP_DIR_RE = re.compile(r'^\d{8}T\d{6}Z(?:-[A-Za-z0-9._-]+)?$')


def fail(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def require_git_repo(repo_path: str) -> Path:
    repo = Path(repo_path)
    if not repo.exists():
        fail(f'repo path does not exist: {repo}')
    if not repo.is_dir():
        fail(f'repo path is not a directory: {repo}')
    inside = subprocess.run(
        ['git', '-C', str(repo), 'rev-parse', '--is-inside-work-tree'],
        text=True,
        capture_output=True,
    )
    if inside.returncode != 0 or inside.stdout.strip() != 'true':
        fail(f'repo path is not a git worktree: {repo}')
    return repo


def repo_status(repo: Path) -> dict:
    status = subprocess.run(
        ['git', '-C', str(repo), 'status', '--porcelain'],
        text=True,
        capture_output=True,
    )
    if status.returncode != 0:
        fail(f'could not read git status for repo path: {repo}')
    branch = subprocess.run(
        ['git', '-C', str(repo), 'branch', '--show-current'],
        text=True,
        capture_output=True,
    )
    head = subprocess.run(
        ['git', '-C', str(repo), 'rev-parse', 'HEAD'],
        text=True,
        capture_output=True,
    )
    return {
        'clean': not status.stdout.strip(),
        'branch': branch.stdout.strip(),
        'head': head.stdout.strip(),
    }


def require_clean_git_repo(repo_path: str) -> Path:
    repo = require_git_repo(repo_path)
    status = subprocess.run(
        ['git', '-C', str(repo), 'status', '--porcelain'],
        text=True,
        capture_output=True,
    )
    if status.returncode != 0:
        fail(f'could not determine git status for repo path: {repo}')
    if status.stdout.strip():
        fail(f'repo path is dirty; commit or stash changes before backup: {repo}')
    return repo


def sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith('sqlite:///'):
        fail(f'unsupported database_url for phase 1 ops automation: {database_url}')
    return Path(database_url.removeprefix('sqlite:///'))


def require_sqlite_db(database_url: str) -> Path:
    db_path = sqlite_path_from_url(database_url)
    if not db_path.exists():
        fail(f'sqlite database path does not exist: {db_path}')
    return db_path


def require_artifacts(artifact_path: str) -> Path:
    path = Path(artifact_path)
    if not path.exists():
        fail(f'artifact path does not exist: {path}')
    if not path.is_dir():
        fail(f'artifact path is not a directory: {path}')
    if not (path / 'ai-index.json').exists():
        fail(f'artifact path is missing ai-index.json: {path / "ai-index.json"}')
    if not (path / 'catalog').is_dir():
        fail(f'artifact path is missing catalog/: {path / "catalog"}')
    return path


def require_backup_root(path: str) -> Path:
    root = Path(path)
    if not root.exists():
        fail(f'backup root does not exist: {root}')
    if not root.is_dir():
        fail(f'backup root is not a directory: {root}')
    return root


def require_keep_last(value: int) -> int:
    if value < 1:
        fail(f'keep-last must be at least 1: {value}')
    return value


def git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(['git', '-C', str(repo), *args], text=True, capture_output=True)
    if result.returncode != 0:
        fail(f'git command failed for {repo}: {" ".join(args)}\n{result.stderr}')
    return result.stdout.strip()


def normalize_health_url(api_url: str) -> str:
    base = api_url.rstrip('/')
    if base.endswith('/healthz'):
        return base
    return f'{base}/healthz'


def check_api(api_url: str) -> dict:
    health_url = normalize_health_url(api_url)
    req = request.Request(health_url, headers={'Accept': 'application/json'})
    try:
        with request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except error.HTTPError as exc:
        fail(f'health endpoint returned HTTP {exc.code}: {health_url}')
    except error.URLError as exc:
        fail(f'health endpoint request failed: {exc.reason}')
    except json.JSONDecodeError as exc:
        fail(f'health endpoint did not return JSON: {exc}')
    if payload.get('ok') is not True:
        fail(f'health endpoint did not report ok=true: {payload}')
    return {'url': health_url, 'ok': True, 'service': payload.get('service') or ''}


def check_repo(repo_path: str) -> dict:
    repo = require_git_repo(repo_path)
    status = repo_status(repo)
    return {
        'path': str(repo),
        'ok': True,
        'clean': status['clean'],
        'branch': status['branch'],
        'head': status['head'],
    }


def check_database(database_url: str) -> dict:
    db_path = sqlite_path_from_url(database_url)
    if not db_path.exists():
        fail(f'sqlite database path does not exist: {db_path}')
    try:
        connection = sqlite3.connect(db_path)
        connection.execute('select 1').fetchone()
    except sqlite3.Error as exc:
        fail(f'sqlite health check failed for {db_path}: {exc}')
    finally:
        if 'connection' in locals():
            connection.close()
    return {'kind': 'sqlite', 'path': str(db_path), 'ok': True}


def check_artifacts(artifact_path: str) -> dict:
    path = require_artifacts(artifact_path)
    return {
        'path': str(path),
        'ok': True,
        'ai_index': True,
        'catalog': True,
    }


def sanitize_label(label: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9._-]+', '-', label.strip()).strip('-')
    return cleaned


def create_backup_dir(output_dir: str, label: str) -> tuple[Path, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    suffix = sanitize_label(label)
    dirname = f'{timestamp}-{suffix}' if suffix else timestamp
    backup_dir = root / dirname
    backup_dir.mkdir()
    return backup_dir, timestamp


def write_repo_bundle(repo: Path, backup_dir: Path) -> str:
    bundle_name = 'repo.bundle'
    bundle_path = backup_dir / bundle_name
    result = subprocess.run(
        ['git', '-C', str(repo), 'bundle', 'create', str(bundle_path), '--all'],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        fail(f'failed to create repo bundle: {result.stderr}')
    return bundle_name


def copy_sqlite_db(db_path: Path, backup_dir: Path) -> str:
    db_name = db_path.name or 'server.db'
    destination = backup_dir / db_name
    shutil.copy2(db_path, destination)
    return db_name


def archive_artifacts(artifact_path: Path, backup_dir: Path) -> str:
    archive_name = 'artifacts.tar.gz'
    archive_path = backup_dir / archive_name
    with tarfile.open(archive_path, 'w:gz') as archive:
        archive.add(artifact_path, arcname='artifacts')
    return archive_name


def classify_backup_entries(root: Path) -> tuple[list[Path], list[Path]]:
    eligible = []
    ignored = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            ignored.append(entry)
            continue
        if not BACKUP_DIR_RE.match(entry.name):
            ignored.append(entry)
            continue
        if not (entry / 'manifest.json').is_file():
            ignored.append(entry)
            continue
        eligible.append(entry)
    return eligible, ignored


def build_prune_summary(root: Path, keep_last: int) -> dict:
    eligible, ignored = classify_backup_entries(root)
    eligible_desc = sorted(eligible, key=lambda item: item.name, reverse=True)
    kept = eligible_desc[:keep_last]
    deleted = eligible_desc[keep_last:]

    for path in deleted:
        shutil.rmtree(path)

    return {
        'ok': True,
        'backup_root': str(root),
        'keep_last': keep_last,
        'kept': [str(path) for path in kept],
        'deleted': [str(path) for path in deleted],
        'ignored': [str(path) for path in ignored],
    }


def render_env_example(args: argparse.Namespace) -> str:
    repo_root = args.repo_root.rstrip('/')
    artifact_path = args.artifact_path or f'{repo_root}/artifacts'
    database_url = args.database_url or f'sqlite:///{repo_root}/data/server.db'
    repo_lock_path = args.repo_lock_path or f'{repo_root}/state/repo.lock'
    bootstrap_users = (
        '[{"username":"maintainer","display_name":"Maintainer","role":"maintainer","token":"replace-maintainer-token"},'
        '{"username":"contributor","display_name":"Contributor","role":"contributor","token":"replace-contributor-token"}]'
    )
    return '\n'.join(
        [
            f'# Copy this file to {args.env_file} and replace placeholder secrets before enabling services.',
            f'INFINITAS_SERVER_DATABASE_URL={database_url}',
            'INFINITAS_SERVER_SECRET_KEY=replace-with-random-secret',
            f'INFINITAS_SERVER_BOOTSTRAP_USERS={bootstrap_users}',
            f'INFINITAS_SERVER_REPO_PATH={repo_root}',
            f'INFINITAS_SERVER_ARTIFACT_PATH={artifact_path}',
            f'INFINITAS_SERVER_REPO_LOCK_PATH={repo_lock_path}',
            '# Optional immediate post-publish mirror hook; leave blank to disable.',
            'INFINITAS_SERVER_MIRROR_REMOTE=',
            'INFINITAS_SERVER_MIRROR_BRANCH=',
            '',
        ]
    )


def render_api_service(args: argparse.Namespace) -> str:
    return f"""[Unit]
Description=Infinitas Hosted Registry API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={args.service_user}
WorkingDirectory={args.repo_root}
EnvironmentFile={args.env_file}
ExecStart={args.python_bin} -m uvicorn server.app:app --host {args.listen_host} --port {args.listen_port}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def render_worker_service(args: argparse.Namespace) -> str:
    return f"""[Unit]
Description=Infinitas Hosted Registry Worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={args.service_user}
WorkingDirectory={args.repo_root}
EnvironmentFile={args.env_file}
Environment=PYTHONPATH={args.repo_root.rstrip("/")}/src
ExecStart={args.python_bin} -m infinitas_skill.cli.main server worker --poll-interval {args.worker_poll_interval:g}
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
"""


def render_backup_service(args: argparse.Namespace) -> str:
    artifact_path = args.artifact_path or f'{args.repo_root.rstrip("/")}/artifacts'
    database_url = args.database_url or f'sqlite:///{args.repo_root.rstrip("/")}/data/server.db'
    return f"""[Unit]
Description=Infinitas Hosted Registry Backup
After=network-online.target

[Service]
Type=oneshot
User={args.service_user}
WorkingDirectory={args.repo_root}
EnvironmentFile={args.env_file}
ExecStart={args.python_bin} {args.repo_root}/scripts/backup-hosted-registry.py --repo-path {args.repo_root} --database-url {database_url} --artifact-path {artifact_path} --output-dir {args.backup_output_dir} --label {args.backup_label}
"""


def render_backup_timer(args: argparse.Namespace) -> str:
    return f"""[Unit]
Description=Schedule Infinitas Hosted Registry backups

[Timer]
OnCalendar={args.backup_on_calendar}
Persistent=true
Unit={args.service_prefix}-backup.service

[Install]
WantedBy=timers.target
"""


def render_prune_service(args: argparse.Namespace) -> str:
    return f"""[Unit]
Description=Infinitas Hosted Registry Backup Retention Prune
After=network-online.target

[Service]
Type=oneshot
User={args.service_user}
WorkingDirectory={args.repo_root}
ExecStart={args.python_bin} {args.repo_root}/scripts/prune-hosted-backups.py --backup-root {args.backup_output_dir} --keep-last {args.prune_keep_last} --json
"""


def render_prune_timer(args: argparse.Namespace) -> str:
    return f"""[Unit]
Description=Schedule Infinitas Hosted Registry backup pruning

[Timer]
OnCalendar={args.prune_on_calendar}
Persistent=true
Unit={args.service_prefix}-prune.service

[Install]
WantedBy=timers.target
"""


def render_mirror_service(args: argparse.Namespace) -> str:
    extra_flags = ''
    if args.mirror_branch:
        extra_flags = f' --branch {args.mirror_branch}'
    return f"""[Unit]
Description=Infinitas Hosted Registry One-Way Mirror Push
After=network-online.target

[Service]
Type=oneshot
User={args.service_user}
WorkingDirectory={args.repo_root}
ExecStart=/usr/bin/env bash {args.repo_root}/scripts/mirror-registry.sh --remote {args.mirror_remote}{extra_flags}
"""


def render_mirror_timer(args: argparse.Namespace) -> str:
    return f"""[Unit]
Description=Schedule Infinitas Hosted Registry outward mirroring

[Timer]
OnCalendar={args.mirror_on_calendar}
Persistent=true
Unit={args.service_prefix}-mirror.service

[Install]
WantedBy=timers.target
"""


def render_inspect_service(args: argparse.Namespace) -> str:
    database_url = args.database_url or f'sqlite:///{args.repo_root.rstrip("/")}/data/server.db'
    extra = []
    if args.inspect_max_queued_jobs is not None:
        extra.extend(['--max-queued-jobs', str(args.inspect_max_queued_jobs)])
    if args.inspect_max_running_jobs is not None:
        extra.extend(['--max-running-jobs', str(args.inspect_max_running_jobs)])
    if args.inspect_max_failed_jobs is not None:
        extra.extend(['--max-failed-jobs', str(args.inspect_max_failed_jobs)])
    if args.inspect_max_warning_jobs is not None:
        extra.extend(['--max-warning-jobs', str(args.inspect_max_warning_jobs)])
    if args.inspect_alert_webhook_url:
        extra.extend(['--alert-webhook-url', args.inspect_alert_webhook_url])
    if args.inspect_alert_fallback_file:
        extra.extend(['--alert-fallback-file', args.inspect_alert_fallback_file])
    extra_flags = ' '.join(extra)
    if extra_flags:
        extra_flags = f' {extra_flags}'
    return f"""[Unit]
Description=Infinitas Hosted Registry Queue Inspection
After=network-online.target

[Service]
Type=oneshot
User={args.service_user}
WorkingDirectory={args.repo_root}
EnvironmentFile={args.env_file}
Environment=PYTHONPATH={args.repo_root.rstrip("/")}/src
ExecStart={args.python_bin} -m infinitas_skill.cli.main server inspect-state --database-url {database_url} --limit {args.inspect_limit} --json{extra_flags}
"""


def render_inspect_timer(args: argparse.Namespace) -> str:
    return f"""[Unit]
Description=Schedule Infinitas Hosted Registry inspections

[Timer]
OnCalendar={args.inspect_on_calendar}
Persistent=true
Unit={args.service_prefix}-inspect.service

[Install]
WantedBy=timers.target
"""


def write_file(path: Path, content: str):
    path.write_text(content, encoding='utf-8')
    print(f'wrote {path}')


def emit(summary: dict, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: api {summary['api']['url']}")
    print(f"OK: repo {summary['repo']['path']} (clean={summary['repo']['clean']})")
    print(f"OK: artifacts {summary['artifacts']['path']}")
    print(f"OK: database {summary['database']['path']}")


def emit_backup_summary(summary: dict, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: backup dir {summary['backup_dir']}")
    print(f"OK: repo bundle {summary['files']['repo_bundle']}")
    print(f"OK: sqlite copy {summary['files']['database']}")
    print(f"OK: artifact archive {summary['files']['artifacts']}")


def emit_prune_summary(summary: dict, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: backup root {summary['backup_root']}")
    print(f"OK: kept {len(summary['kept'])} recognized backup directories")
    print(f"OK: deleted {len(summary['deleted'])} recognized backup directories")
    if summary['ignored']:
        print(f"OK: ignored {len(summary['ignored'])} non-hosted entries")


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


def run_server_healthcheck(
    *,
    api_url: str,
    repo_path: str,
    artifact_path: str,
    database_url: str,
    token: str = '',
    as_json: bool = False,
) -> int:
    _ = token
    summary = {
        'ok': True,
        'api': check_api(api_url),
        'repo': check_repo(repo_path),
        'artifacts': check_artifacts(artifact_path),
        'database': check_database(database_url),
    }
    emit(summary, as_json=as_json)
    return 0


def run_server_backup(
    *,
    repo_path: str,
    database_url: str,
    artifact_path: str,
    output_dir: str,
    label: str = '',
    as_json: bool = False,
) -> int:
    repo = require_clean_git_repo(repo_path)
    db_path = require_sqlite_db(database_url)
    artifacts = require_artifacts(artifact_path)
    backup_dir, timestamp = create_backup_dir(output_dir, label)

    repo_bundle_name = write_repo_bundle(repo, backup_dir)
    db_copy_name = copy_sqlite_db(db_path, backup_dir)
    artifacts_name = archive_artifacts(artifacts, backup_dir)

    manifest = {
        'created_at': timestamp,
        'label': label,
        'repo': {
            'path': str(repo),
            'head': git_output(repo, 'rev-parse', 'HEAD'),
            'branch': git_output(repo, 'branch', '--show-current'),
            'bundle': repo_bundle_name,
        },
        'database': {
            'kind': 'sqlite',
            'url': database_url,
            'path': str(db_path),
            'backup_file': db_copy_name,
        },
        'artifacts': {
            'path': str(artifacts),
            'archive': artifacts_name,
        },
    }
    manifest_name = 'manifest.json'
    (backup_dir / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    summary = {
        'ok': True,
        'backup_dir': str(backup_dir),
        'manifest': str(backup_dir / manifest_name),
        'files': {
            'repo_bundle': repo_bundle_name,
            'database': db_copy_name,
            'artifacts': artifacts_name,
            'manifest': manifest_name,
        },
    }
    emit_backup_summary(summary, as_json=as_json)
    return 0


def run_server_render_systemd(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_file(output_dir / f'{args.service_prefix}.env.example', render_env_example(args))
    write_file(output_dir / f'{args.service_prefix}-api.service', render_api_service(args))
    write_file(output_dir / f'{args.service_prefix}-worker.service', render_worker_service(args))
    write_file(output_dir / f'{args.service_prefix}-backup.service', render_backup_service(args))
    write_file(output_dir / f'{args.service_prefix}-backup.timer', render_backup_timer(args))
    if args.mirror_remote:
        write_file(output_dir / f'{args.service_prefix}-mirror.service', render_mirror_service(args))
        write_file(output_dir / f'{args.service_prefix}-mirror.timer', render_mirror_timer(args))
    write_file(output_dir / f'{args.service_prefix}-prune.service', render_prune_service(args))
    write_file(output_dir / f'{args.service_prefix}-prune.timer', render_prune_timer(args))
    write_file(output_dir / f'{args.service_prefix}-inspect.service', render_inspect_service(args))
    write_file(output_dir / f'{args.service_prefix}-inspect.timer', render_inspect_timer(args))
    return 0


def run_server_prune_backups(*, backup_root: str, keep_last: int, as_json: bool = False) -> int:
    root = require_backup_root(backup_root)
    count = require_keep_last(keep_last)
    summary = build_prune_summary(root, count)
    emit_prune_summary(summary, as_json=as_json)
    return 0


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
