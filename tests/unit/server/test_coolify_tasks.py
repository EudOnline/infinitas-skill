from __future__ import annotations

from typing import Any

import pytest

from infinitas_skill.server import coolify_tasks


@pytest.mark.parametrize(
    ("task", "target", "expected"),
    [
        (
            "backup",
            "run_server_backup",
            {
                "repo_path": "/srv/infinitas/repo",
                "database_url": "sqlite:////srv/infinitas/data/server.db",
                "artifact_path": "/srv/infinitas/artifacts",
                "output_dir": "/srv/infinitas/backups",
                "label": "scheduled",
                "lock_path": "/srv/infinitas/data/repo.lock",
                "lock_timeout_seconds": 120,
                "as_json": True,
            },
        ),
        (
            "prune",
            "run_server_prune_backups",
            {
                "backup_root": "/srv/infinitas/backups",
                "keep_last": 48,
                "require_offsite_receipt": True,
                "receipt_root": "/srv/infinitas/backup-receipts",
                "as_json": True,
            },
        ),
        (
            "inspect",
            "run_server_inspect_backup_state",
            {
                "backup_root": "/srv/infinitas/backups",
                "receipt_root": "/srv/infinitas/backup-receipts",
                "max_local_age_hours": 2,
                "max_offsite_age_hours": 3,
                "as_json": True,
            },
        ),
    ],
)
def test_coolify_task_uses_fixed_hosted_paths(
    monkeypatch: pytest.MonkeyPatch,
    task: str,
    target: str,
    expected: dict[str, Any],
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(coolify_tasks, target, lambda **kwargs: calls.append(kwargs) or 0)

    assert coolify_tasks.run_coolify_task(task) == 0
    assert calls == [expected]


def test_coolify_export_uses_backup_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setenv("INFINITAS_BACKUP_WEBDAV_URL", "https://storage.example/dav")
    monkeypatch.setenv("INFINITAS_BACKUP_REMOTE_PREFIX", "registry.example")
    monkeypatch.setenv("INFINITAS_BACKUP_AGE_RECIPIENT", "age1test")
    monkeypatch.setattr(
        coolify_tasks, "run_server_export_backups", lambda **kwargs: calls.append(kwargs) or 0
    )

    assert coolify_tasks.run_coolify_task("export") == 0
    assert calls == [
        {
            "backup_root": "/srv/infinitas/backups",
            "staging_dir": "/srv/infinitas/backup-staging",
            "receipt_root": "/srv/infinitas/backup-receipts",
            "webdav_url": "https://storage.example/dav",
            "remote_prefix": "registry.example",
            "age_recipient": "age1test",
            "auth_mode": "basic",
            "user_env": "INFINITAS_BACKUP_WEBDAV_USER",
            "secret_env": "INFINITAS_BACKUP_WEBDAV_PASSWORD",
            "as_json": True,
        }
    ]


def test_coolify_task_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="unknown Coolify task"):
        coolify_tasks.run_coolify_task("unknown")
