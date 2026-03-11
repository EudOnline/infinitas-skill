#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from schema_version_lib import SUPPORTED_SCHEMA_VERSION, validate_schema_version


class MigrationError(Exception):
    pass


def iter_meta_paths(raw_paths):
    seen = set()
    for raw in raw_paths:
        path = Path(raw).resolve()
        if path.is_file():
            if path.name != '_meta.json':
                raise MigrationError(f'expected a _meta.json file, got {path}')
            if path not in seen:
                seen.add(path)
                yield path
            continue
        if not path.exists():
            raise MigrationError(f'path does not exist: {path}')
        direct = path / '_meta.json'
        if direct.is_file():
            resolved = direct.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved
            continue
        for candidate in sorted(path.rglob('_meta.json')):
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved


def migrate_meta(path: Path, *, check=False):
    payload = json.loads(path.read_text(encoding='utf-8'))
    _version, errors = validate_schema_version(payload)
    if errors:
        raise MigrationError(f"{path}: {'; '.join(errors)}")
    if payload.get('schema_version') == SUPPORTED_SCHEMA_VERSION:
        return False
    if check:
        print(f'{path}: would update schema_version to {SUPPORTED_SCHEMA_VERSION}')
        return True
    payload = {'schema_version': SUPPORTED_SCHEMA_VERSION, **payload}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{path}: wrote schema_version {SUPPORTED_SCHEMA_VERSION}')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()

    try:
        meta_paths = list(iter_meta_paths(args.paths))
    except MigrationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not meta_paths:
        print('no _meta.json files found', file=sys.stderr)
        return 1

    changed = False
    try:
        for path in meta_paths:
            changed = migrate_meta(path, check=args.check) or changed
    except MigrationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.check and changed:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
