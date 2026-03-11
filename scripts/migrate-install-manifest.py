#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from install_manifest_lib import InstallManifestError, MANIFEST_FILENAME, manifest_path_for, normalize_install_manifest, write_install_manifest
from schema_version_lib import SUPPORTED_SCHEMA_VERSION, validate_schema_version


def load_payload(manifest_path: Path):
    try:
        return json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise InstallManifestError(f'invalid install manifest JSON: {exc}') from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('path')
    args = parser.parse_args()

    target = Path(args.path).resolve()
    manifest_path = target if target.name == MANIFEST_FILENAME else manifest_path_for(target)
    if not manifest_path.exists():
        print(f'no manifest found: {manifest_path}')
        return 0

    try:
        payload = load_payload(manifest_path)
        _version, errors = validate_schema_version(payload)
        if errors and payload.get('schema_version') is not None:
            raise InstallManifestError('; '.join(errors))
        normalize_install_manifest(payload)
    except InstallManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if payload.get('schema_version') == SUPPORTED_SCHEMA_VERSION:
        print(f'{manifest_path}: already at schema_version {SUPPORTED_SCHEMA_VERSION}')
        return 0

    if args.check:
        print(f'{manifest_path}: would write schema_version {SUPPORTED_SCHEMA_VERSION}')
        return 1

    write_install_manifest(manifest_path, payload)
    print(f'{manifest_path}: wrote schema_version {SUPPORTED_SCHEMA_VERSION}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
