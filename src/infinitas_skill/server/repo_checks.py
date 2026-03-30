"""Repository and filesystem validation helpers for hosted server commands."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


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


__all__ = [
    'check_artifacts',
    'check_database',
    'check_repo',
    'fail',
    'git_output',
    'repo_status',
    'require_artifacts',
    'require_backup_root',
    'require_clean_git_repo',
    'require_git_repo',
    'require_keep_last',
    'require_sqlite_db',
    'sqlite_path_from_url',
]
