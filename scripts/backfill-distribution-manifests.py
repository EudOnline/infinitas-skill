#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from distribution_lib import (
    DistributionError,
    build_distribution_manifest_payload,
    infer_distribution_root,
    verify_distribution_manifest,
)
from release_lib import ROOT


def parse_args():
    parser = argparse.ArgumentParser(description='Backfill legacy distribution manifest reproducibility metadata')
    parser.add_argument('--manifest', required=True, help='Path to one distribution manifest JSON file')
    parser.add_argument('--write', action='store_true', help='Write in-place when metadata can be backfilled')
    parser.add_argument('--json', action='store_true', help='Print machine-readable status')
    return parser.parse_args()


def _is_missing_additive_field(payload, key):
    value = payload.get(key)
    if value is None:
        return True
    if key == 'file_manifest':
        return not isinstance(value, list) or not value
    if key == 'build':
        return not isinstance(value, dict) or not value
    return False


def _emit(payload, as_json):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        state = payload.get('state')
        manifest = payload.get('manifest')
        if state == 'backfilled':
            print(f'OK: backfilled {manifest}')
        elif state == 'would-backfill':
            print(f'OK: would-backfill {manifest}')
        elif state == 'unchanged':
            print(f'OK: unchanged {manifest}')
        else:
            print(f'FAIL: {payload.get("error")}', file=sys.stderr)


def main():
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        payload = {'state': 'incomplete-evidence', 'manifest': str(manifest_path), 'error': 'manifest file is missing'}
        _emit(payload, args.json)
        return 1

    manifest_root = infer_distribution_root(manifest_path)
    try:
        verified = verify_distribution_manifest(manifest_path, root=manifest_root, attestation_root=ROOT)
        current_payload = verified.get('manifest') or {}
        canonical_payload = build_distribution_manifest_payload(
            verified['provenance_path'],
            verified['bundle_path'],
            root=manifest_root,
            attestation_root=ROOT,
        )
    except DistributionError as exc:
        payload = {'state': 'incomplete-evidence', 'manifest': str(manifest_path), 'error': str(exc)}
        _emit(payload, args.json)
        return 1

    rewritten = json.loads(json.dumps(current_payload))
    changed_fields = []
    for key in ['file_manifest', 'build']:
        if _is_missing_additive_field(rewritten, key):
            rewritten[key] = canonical_payload.get(key)
            changed_fields.append(key)

    state = 'unchanged'
    if changed_fields:
        state = 'backfilled' if args.write else 'would-backfill'
    wrote = False
    if state == 'backfilled':
        manifest_path.write_text(json.dumps(rewritten, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        wrote = True

    payload = {
        'state': state,
        'manifest': str(manifest_path),
        'root': str(manifest_root),
        'changed_fields': changed_fields,
        'wrote': wrote,
    }
    _emit(payload, args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
