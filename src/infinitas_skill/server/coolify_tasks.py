"""Short scheduled-task entrypoints for the supported Coolify layout."""

from __future__ import annotations

import os
from collections.abc import Callable

from infinitas_skill.server.backup import run_server_backup, run_server_prune_backups
from infinitas_skill.server.backup_export import (
    run_server_export_backups,
    run_server_inspect_backup_state,
)

BACKUP_ROOT = "/srv/infinitas/backups"
RECEIPT_ROOT = "/srv/infinitas/backup-receipts"
COOLIFY_TASK_NAMES = ("backup", "export", "prune", "inspect")


def _run_backup() -> int:
    return run_server_backup(
        repo_path="/srv/infinitas/repo",
        database_url="sqlite:////srv/infinitas/data/server.db",
        artifact_path="/srv/infinitas/artifacts",
        output_dir=BACKUP_ROOT,
        label="scheduled",
        lock_path="/srv/infinitas/data/repo.lock",
        lock_timeout_seconds=120,
        as_json=True,
    )


def _run_export() -> int:
    return run_server_export_backups(
        backup_root=BACKUP_ROOT,
        staging_dir="/srv/infinitas/backup-staging",
        receipt_root=RECEIPT_ROOT,
        webdav_url=os.environ.get(
            "INFINITAS_BACKUP_WEBDAV_URL", "https://openlist.infinitas.fun/dav"
        ),
        remote_prefix=os.environ.get("INFINITAS_BACKUP_REMOTE_PREFIX", "skills.infinitas.fun"),
        age_recipient=os.environ.get("INFINITAS_BACKUP_AGE_RECIPIENT", ""),
        auth_mode="basic",
        user_env="INFINITAS_BACKUP_WEBDAV_USER",
        secret_env="INFINITAS_BACKUP_WEBDAV_PASSWORD",  # noqa: S106 - environment name
        as_json=True,
    )


def _run_prune() -> int:
    return run_server_prune_backups(
        backup_root=BACKUP_ROOT,
        keep_last=48,
        require_offsite_receipt=True,
        receipt_root=RECEIPT_ROOT,
        as_json=True,
    )


def _run_inspect() -> int:
    return run_server_inspect_backup_state(
        backup_root=BACKUP_ROOT,
        receipt_root=RECEIPT_ROOT,
        max_local_age_hours=2,
        max_offsite_age_hours=3,
        as_json=True,
    )


_TASKS: dict[str, Callable[[], int]] = {
    "backup": _run_backup,
    "export": _run_export,
    "prune": _run_prune,
    "inspect": _run_inspect,
}


def run_coolify_task(task: str) -> int:
    try:
        handler = _TASKS[task]
    except KeyError as exc:
        raise ValueError(f"unknown Coolify task: {task}") from exc
    return handler()


__all__ = ["COOLIFY_TASK_NAMES", "run_coolify_task"]
