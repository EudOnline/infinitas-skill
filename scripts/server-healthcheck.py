#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib import error, request


def fail(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Hosted registry server health check')
    parser.add_argument('--api-url', required=True, help='Hosted registry API base URL or /healthz URL')
    parser.add_argument('--repo-path', required=True, help='Path to the server-owned git checkout')
    parser.add_argument('--artifact-path', required=True, help='Path to the hosted artifact directory')
    parser.add_argument('--database-url', required=True, help='Database URL, currently sqlite:///... only')
    parser.add_argument('--token', default='', help='Reserved for future authenticated probes')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser.parse_args()


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
        'path': str(repo),
        'ok': True,
        'clean': not status.stdout.strip(),
        'branch': branch.stdout.strip(),
        'head': head.stdout.strip(),
    }


def sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith('sqlite:///'):
        fail(f'unsupported database_url for phase 1 ops automation: {database_url}')
    return Path(database_url.removeprefix('sqlite:///'))


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
    path = Path(artifact_path)
    if not path.exists():
        fail(f'artifact path does not exist: {path}')
    if not path.is_dir():
        fail(f'artifact path is not a directory: {path}')
    ai_index = path / 'ai-index.json'
    if not ai_index.exists():
        fail(f'artifact path is missing ai-index.json: {ai_index}')
    catalog = path / 'catalog'
    if not catalog.exists() or not catalog.is_dir():
        fail(f'artifact path is missing catalog/: {catalog}')
    return {
        'path': str(path),
        'ok': True,
        'ai_index': True,
        'catalog': True,
    }


def emit(summary: dict, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: api {summary['api']['url']}")
    print(f"OK: repo {summary['repo']['path']} (clean={summary['repo']['clean']})")
    print(f"OK: artifacts {summary['artifacts']['path']}")
    print(f"OK: database {summary['database']['path']}")


def main():
    args = parse_args()
    summary = {
        'ok': True,
        'api': check_api(args.api_url),
        'repo': check_repo(args.repo_path),
        'artifacts': check_artifacts(args.artifact_path),
        'database': check_database(args.database_url),
    }
    emit(summary, as_json=args.json)


if __name__ == '__main__':
    main()
