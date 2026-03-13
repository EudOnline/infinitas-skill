#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

BACKUP_DIR_RE = re.compile(r'^\d{8}T\d{6}Z(?:-[A-Za-z0-9._-]+)?$')


def fail(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Prune older hosted registry backup snapshots')
    parser.add_argument('--backup-root', required=True, help='Directory containing hosted backup snapshot directories')
    parser.add_argument('--keep-last', required=True, type=int, help='How many newest recognized backup directories to keep')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON output')
    return parser.parse_args()


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


def classify_entries(root: Path) -> tuple[list[Path], list[Path]]:
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


def build_summary(root: Path, keep_last: int) -> dict:
    eligible, ignored = classify_entries(root)
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


def emit(summary: dict, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: backup root {summary['backup_root']}")
    print(f"OK: kept {len(summary['kept'])} recognized backup directories")
    print(f"OK: deleted {len(summary['deleted'])} recognized backup directories")
    if summary['ignored']:
        print(f"OK: ignored {len(summary['ignored'])} non-hosted entries")


def main():
    args = parse_args()
    root = require_backup_root(args.backup_root)
    keep_last = require_keep_last(args.keep_last)
    summary = build_summary(root, keep_last)
    emit(summary, as_json=args.json)


if __name__ == '__main__':
    main()
