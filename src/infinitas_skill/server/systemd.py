"""systemd rendering helpers for hosted server commands."""

from __future__ import annotations

import argparse
from pathlib import Path


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
            'INFINITAS_SERVER_ENV=production',
            'INFINITAS_SERVER_ALLOWED_HOSTS=["127.0.0.1","localhost"]',
            f'INFINITAS_SERVER_DATABASE_URL={database_url}',
            'INFINITAS_SERVER_SECRET_KEY=replace-with-random-secret',
            f'INFINITAS_SERVER_BOOTSTRAP_USERS={bootstrap_users}',
            f'INFINITAS_SERVER_REPO_PATH={repo_root}',
            f'INFINITAS_SERVER_ARTIFACT_PATH={artifact_path}',
            f'INFINITAS_SERVER_REPO_LOCK_PATH={repo_lock_path}',
            '# Optional immediate post-publish mirror hook; leave blank to disable.',
            'INFINITAS_SERVER_MIRROR_REMOTE=',
            'INFINITAS_SERVER_MIRROR_BRANCH=',
            '# Optional scheduled memory curation policy.',
            f'INFINITAS_SERVER_MEMORY_CURATION_ACTION={args.curation_action}',
            'INFINITAS_SERVER_MEMORY_CURATION_APPLY=1',
            'INFINITAS_SERVER_MEMORY_CURATION_LIMIT=50',
            f'INFINITAS_SERVER_MEMORY_CURATION_MAX_ACTIONS={args.curation_max_actions}',
            'INFINITAS_SERVER_MEMORY_CURATION_ACTOR_REF=system:openclaw-background-task:memory-curation',
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
Environment=PYTHONPATH={args.repo_root.rstrip("/")}/src
ExecStart={args.python_bin} -m infinitas_skill.cli.main server backup --repo-path {args.repo_root} --database-url {database_url} --artifact-path {artifact_path} --output-dir {args.backup_output_dir} --label {args.backup_label}
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
Environment=PYTHONPATH={args.repo_root.rstrip("/")}/src
ExecStart={args.python_bin} -m infinitas_skill.cli.main server prune-backups --backup-root {args.backup_output_dir} --keep-last {args.prune_keep_last} --json
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


def render_memory_curation_service(args: argparse.Namespace) -> str:
    database_url = args.database_url or f'sqlite:///{args.repo_root.rstrip("/")}/data/server.db'
    return f"""[Unit]
Description=Infinitas OpenClaw Runtime Memory Maintenance Background Task Enqueue
After=network-online.target

[Service]
Type=oneshot
User={args.service_user}
WorkingDirectory={args.repo_root}
EnvironmentFile={args.env_file}
Environment=PYTHONPATH={args.repo_root.rstrip("/")}/src
ExecStart={args.python_bin} -m infinitas_skill.cli.main server memory-curation --database-url {database_url} --use-server-policy --enqueue --json
"""


def render_memory_curation_timer(args: argparse.Namespace) -> str:
    return f"""[Unit]
Description=Schedule Infinitas OpenClaw runtime memory maintenance

[Timer]
OnCalendar={args.curation_on_calendar}
Persistent=true
Unit={args.service_prefix}-memory-curation.service

[Install]
WantedBy=timers.target
"""


def write_file(path: Path, content: str):
    path.write_text(content, encoding='utf-8')
    print(f'wrote {path}')


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
    if args.curation_on_calendar:
        write_file(
            output_dir / f'{args.service_prefix}-memory-curation.service',
            render_memory_curation_service(args),
        )
        write_file(
            output_dir / f'{args.service_prefix}-memory-curation.timer',
            render_memory_curation_timer(args),
        )
    return 0


__all__ = [
    'render_api_service',
    'render_backup_service',
    'render_backup_timer',
    'render_env_example',
    'render_inspect_service',
    'render_inspect_timer',
    'render_memory_curation_service',
    'render_memory_curation_timer',
    'render_mirror_service',
    'render_mirror_timer',
    'render_prune_service',
    'render_prune_timer',
    'render_worker_service',
    'run_server_render_systemd',
    'write_file',
]
