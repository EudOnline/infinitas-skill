#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render a hosted registry systemd deployment bundle')
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
    parser.add_argument('--artifact-path', default='', help='Override artifact path for the env template and backup service')
    parser.add_argument('--database-url', default='', help='Override database URL for the env template and backup service')
    parser.add_argument('--repo-lock-path', default='', help='Override repo lock path for the env template')
    return parser.parse_args()


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
ExecStart={args.python_bin} {args.repo_root}/scripts/run-hosted-worker.py --poll-interval {args.worker_poll_interval:g}
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
ExecStart={args.python_bin} {args.repo_root}/scripts/inspect-hosted-state.py --database-url {database_url} --limit {args.inspect_limit} --json{extra_flags}
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


def main():
    args = parse_args()
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


if __name__ == '__main__':
    main()
