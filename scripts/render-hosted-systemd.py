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


if __name__ == '__main__':
    main()
