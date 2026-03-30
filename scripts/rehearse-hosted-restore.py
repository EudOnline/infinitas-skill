#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from pathlib import Path


def fail(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Rehearse restoring a hosted registry backup into a staging directory')
    parser.add_argument('--backup-dir', required=True, help='Backup directory created by `infinitas server backup`')
    parser.add_argument('--output-dir', required=True, help='Staging directory for the restore rehearsal')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser.parse_args()


def load_manifest(backup_dir: Path) -> dict:
    manifest_path = backup_dir / 'manifest.json'
    if not manifest_path.exists():
        fail(f'backup directory is missing manifest.json: {manifest_path}')
    try:
        payload = json.loads(manifest_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        fail(f'invalid manifest.json in {backup_dir}: {exc}')
    if not isinstance(payload, dict):
        fail(f'manifest.json must contain an object: {manifest_path}')
    return payload


def require_child(backup_dir: Path, relative_name: str, label: str) -> Path:
    path = backup_dir / relative_name
    if not path.exists():
        fail(f'backup directory is missing {label}: {path}')
    return path


def verify_bundle(bundle_path: Path):
    result = subprocess.run(['git', 'bundle', 'verify', str(bundle_path)], text=True, capture_output=True)
    if result.returncode != 0:
        fail(f'git bundle verify failed for {bundle_path}\n{result.stderr}')


def clone_bundle(bundle_path: Path, output_repo: Path):
    result = subprocess.run(['git', 'clone', str(bundle_path), str(output_repo)], text=True, capture_output=True)
    if result.returncode != 0:
        fail(f'git clone failed for {bundle_path}\n{result.stderr}')


def copy_and_verify_sqlite(source_db: Path, target_db: Path):
    shutil.copy2(source_db, target_db)
    try:
        conn = sqlite3.connect(target_db)
        conn.execute('select 1').fetchone()
    except sqlite3.Error as exc:
        fail(f'sqlite verification failed for restored db {target_db}: {exc}')
    finally:
        if 'conn' in locals():
            conn.close()


def extract_artifacts(archive_path: Path, output_dir: Path) -> Path:
    with tarfile.open(archive_path, 'r:gz') as archive:
        archive.extractall(output_dir)
    artifacts_dir = output_dir / 'artifacts'
    if not (artifacts_dir / 'ai-index.json').exists():
        fail(f'restored artifacts are missing ai-index.json: {artifacts_dir / "ai-index.json"}')
    if not (artifacts_dir / 'catalog').is_dir():
        fail(f'restored artifacts are missing catalog/: {artifacts_dir / "catalog"}')
    return artifacts_dir


def emit(summary: dict, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: manifest label {summary['manifest'].get('label', '')}")
    print(f"OK: cloned repo to {summary['paths']['repo']}")
    print(f"OK: copied sqlite db to {summary['paths']['database']}")
    print(f"OK: extracted artifacts to {summary['paths']['artifacts']}")


def main():
    args = parse_args()
    backup_dir = Path(args.backup_dir).resolve()
    if not backup_dir.is_dir():
        fail(f'backup-dir is not a directory: {backup_dir}')
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(backup_dir)
    repo_bundle_name = (((manifest.get('repo') or {}).get('bundle')) or '').strip()
    db_backup_name = (((manifest.get('database') or {}).get('backup_file')) or '').strip()
    artifacts_archive_name = (((manifest.get('artifacts') or {}).get('archive')) or '').strip()
    if not repo_bundle_name or not db_backup_name or not artifacts_archive_name:
        fail(f'manifest.json is missing required backup file references: {backup_dir / "manifest.json"}')

    bundle_path = require_child(backup_dir, repo_bundle_name, 'repo bundle')
    db_path = require_child(backup_dir, db_backup_name, 'database backup')
    archive_path = require_child(backup_dir, artifacts_archive_name, 'artifact archive')

    verify_bundle(bundle_path)

    repo_output = output_dir / 'repo'
    db_output = output_dir / db_backup_name
    if repo_output.exists():
        shutil.rmtree(repo_output)
    if db_output.exists():
        db_output.unlink()
    clone_bundle(bundle_path, repo_output)
    copy_and_verify_sqlite(db_path, db_output)
    artifacts_output = extract_artifacts(archive_path, output_dir)

    summary = {
        'ok': True,
        'backup_dir': str(backup_dir),
        'manifest': {
            'created_at': manifest.get('created_at'),
            'label': manifest.get('label') or '',
        },
        'paths': {
            'repo': str(repo_output),
            'database': str(db_output),
            'artifacts': str(artifacts_output),
        },
    }
    emit(summary, as_json=args.json)


if __name__ == '__main__':
    main()
