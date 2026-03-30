"""Backup and retention helpers for hosted server commands."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from infinitas_skill.server.repo_checks import (
    fail,
    git_output,
    require_artifacts,
    require_backup_root,
    require_clean_git_repo,
    require_keep_last,
    require_sqlite_db,
)

BACKUP_DIR_RE = re.compile(r'^\d{8}T\d{6}Z(?:-[A-Za-z0-9._-]+)?$')


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


def emit_backup_summary(summary: dict, *, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: backup dir {summary['backup_dir']}")
    print(f"OK: repo bundle {summary['files']['repo_bundle']}")
    print(f"OK: sqlite copy {summary['files']['database']}")
    print(f"OK: artifact archive {summary['files']['artifacts']}")


def emit_prune_summary(summary: dict, *, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: backup root {summary['backup_root']}")
    print(f"OK: kept {len(summary['kept'])} recognized backup directories")
    print(f"OK: deleted {len(summary['deleted'])} recognized backup directories")
    if summary['ignored']:
        print(f"OK: ignored {len(summary['ignored'])} non-hosted entries")


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


def run_server_prune_backups(*, backup_root: str, keep_last: int, as_json: bool = False) -> int:
    root = require_backup_root(backup_root)
    count = require_keep_last(keep_last)
    summary = build_prune_summary(root, count)
    emit_prune_summary(summary, as_json=as_json)
    return 0


__all__ = [
    'BACKUP_DIR_RE',
    'archive_artifacts',
    'build_prune_summary',
    'classify_backup_entries',
    'copy_sqlite_db',
    'create_backup_dir',
    'emit_backup_summary',
    'emit_prune_summary',
    'run_server_backup',
    'run_server_prune_backups',
    'sanitize_label',
    'write_repo_bundle',
]
