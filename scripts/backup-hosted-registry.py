#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def fail(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Create a hosted registry backup set')
    parser.add_argument('--repo-path', required=True, help='Path to the server-owned git checkout')
    parser.add_argument('--database-url', required=True, help='Database URL, currently sqlite:///... only')
    parser.add_argument('--artifact-path', required=True, help='Path to the hosted artifact directory')
    parser.add_argument('--output-dir', required=True, help='Directory where backup snapshots should be created')
    parser.add_argument('--label', default='', help='Optional label appended to the backup directory name')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser.parse_args()


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
    dirty = subprocess.run(
        ['git', '-C', str(repo), 'status', '--porcelain'],
        text=True,
        capture_output=True,
    )
    if dirty.returncode != 0:
        fail(f'could not determine git status for repo path: {repo}')
    if dirty.stdout.strip():
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


def git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(['git', '-C', str(repo), *args], text=True, capture_output=True)
    if result.returncode != 0:
        fail(f'git command failed for {repo}: {" ".join(args)}\n{result.stderr}')
    return result.stdout.strip()


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


def emit(summary: dict, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: backup dir {summary['backup_dir']}")
    print(f"OK: repo bundle {summary['files']['repo_bundle']}")
    print(f"OK: sqlite copy {summary['files']['database']}")
    print(f"OK: artifact archive {summary['files']['artifacts']}")


def main():
    args = parse_args()
    repo = require_git_repo(args.repo_path)
    db_path = require_sqlite_db(args.database_url)
    artifact_path = require_artifacts(args.artifact_path)
    backup_dir, timestamp = create_backup_dir(args.output_dir, args.label)

    repo_bundle_name = write_repo_bundle(repo, backup_dir)
    db_copy_name = copy_sqlite_db(db_path, backup_dir)
    artifacts_name = archive_artifacts(artifact_path, backup_dir)

    manifest = {
        'created_at': timestamp,
        'label': args.label,
        'repo': {
            'path': str(repo),
            'head': git_output(repo, 'rev-parse', 'HEAD'),
            'branch': git_output(repo, 'branch', '--show-current'),
            'bundle': repo_bundle_name,
        },
        'database': {
            'kind': 'sqlite',
            'url': args.database_url,
            'path': str(db_path),
            'backup_file': db_copy_name,
        },
        'artifacts': {
            'path': str(artifact_path),
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
    emit(summary, as_json=args.json)


if __name__ == '__main__':
    main()
