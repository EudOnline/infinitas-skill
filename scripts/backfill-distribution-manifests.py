#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from distribution_lib import (
    DistributionError,
    build_distribution_manifest_payload,
    infer_distribution_root,
    installed_integrity_capability_summary,
    load_json,
    reproducibility_summary,
    verify_distribution_manifest,
)
from release_lib import ROOT


def parse_args():
    parser = argparse.ArgumentParser(description='Backfill legacy distribution manifest reproducibility metadata')
    parser.add_argument('--manifest', action='append', help='Path to one distribution manifest JSON file (repeatable)')
    parser.add_argument('--root', help='Repository root to scan for catalog/distributions/**/manifest.json when --manifest is omitted')
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
        if state == 'scan':
            for item in payload.get('results') or []:
                entry_state = item.get('state')
                entry_manifest = item.get('manifest')
                if entry_state in {'backfilled', 'would-backfill', 'unchanged'}:
                    print(f'OK: {entry_state} {entry_manifest}')
                else:
                    print(f'WARN: {entry_state} {entry_manifest} ({item.get("error")})')
            return
        if state in {'backfilled', 'would-backfill', 'unchanged'}:
            print(f'OK: {state} {manifest}')
            return
        print(f'FAIL: {payload.get("error")}', file=sys.stderr)


def _resolve_manifest_path(root, ref):
    candidate = Path(ref)
    if candidate.is_absolute():
        return candidate.resolve()
    root_candidate = (Path(root).resolve() / candidate).resolve()
    if root_candidate.exists():
        return root_candidate
    return candidate.resolve()


def _scan_manifest_paths(root):
    root = Path(root).resolve()
    distribution_root = root / 'catalog' / 'distributions'
    if not distribution_root.exists():
        return []
    return sorted(path.resolve() for path in distribution_root.rglob('manifest.json'))


def _status_for_payload(payload):
    capability = installed_integrity_capability_summary(payload)
    reproducibility = reproducibility_summary(payload)
    return {
        'file_manifest_count': reproducibility.get('file_manifest_count'),
        'build_archive_format': reproducibility.get('build_archive_format'),
        'installed_integrity_capability': capability.get('installed_integrity_capability'),
        'installed_integrity_reason': capability.get('installed_integrity_reason'),
    }


def _incomplete_status(manifest_path, error, current_payload):
    status = {
        'state': 'incomplete-evidence',
        'manifest': str(manifest_path),
        'error': error,
        'changed_fields': [],
        'wrote': False,
    }
    status.update(_status_for_payload(current_payload))
    return status


def _inspect_manifest(manifest_path, *, write):
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.exists():
        return _incomplete_status(manifest_path, 'manifest file is missing', {})

    try:
        current_payload = load_json(manifest_path)
    except Exception as exc:
        return _incomplete_status(manifest_path, f'could not parse manifest JSON: {exc}', {})

    manifest_root = infer_distribution_root(manifest_path)
    try:
        verified = verify_distribution_manifest(manifest_path, root=manifest_root, attestation_root=ROOT)
        canonical_payload = build_distribution_manifest_payload(
            verified['provenance_path'],
            verified['bundle_path'],
            root=manifest_root,
            attestation_root=ROOT,
        )
    except DistributionError as exc:
        status = _incomplete_status(manifest_path, str(exc), current_payload)
        status['root'] = str(manifest_root)
        return status

    rewritten = json.loads(json.dumps(current_payload))
    changed_fields = []
    for key in ['file_manifest', 'build']:
        if _is_missing_additive_field(rewritten, key):
            rewritten[key] = canonical_payload.get(key)
            changed_fields.append(key)

    state = 'unchanged'
    if changed_fields:
        state = 'backfilled' if write else 'would-backfill'
    wrote = False
    effective_payload = current_payload
    if state == 'backfilled':
        manifest_path.write_text(json.dumps(rewritten, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        wrote = True
        effective_payload = rewritten

    status = {
        'state': state,
        'manifest': str(manifest_path),
        'root': str(manifest_root),
        'changed_fields': changed_fields,
        'wrote': wrote,
    }
    status.update(_status_for_payload(effective_payload))
    return status


def _aggregate_scan_payload(root, results):
    counts = {
        'backfilled': 0,
        'would-backfill': 0,
        'unchanged': 0,
        'incomplete-evidence': 0,
    }
    for item in results:
        state = item.get('state')
        if state in counts:
            counts[state] += 1
    return {
        'state': 'scan',
        'root': str(Path(root).resolve()),
        'inspected_count': len(results),
        'backfilled_count': counts['backfilled'],
        'would_backfill_count': counts['would-backfill'],
        'unchanged_count': counts['unchanged'],
        'incomplete_evidence_count': counts['incomplete-evidence'],
        'results': results,
    }


def main():
    args = parse_args()
    scan_root = Path(args.root or ROOT).resolve()
    if args.manifest:
        manifest_paths = [_resolve_manifest_path(scan_root, ref) for ref in args.manifest]
    else:
        manifest_paths = _scan_manifest_paths(scan_root)

    if not manifest_paths:
        payload = _aggregate_scan_payload(scan_root, [])
        _emit(payload, args.json)
        return 0

    results = [_inspect_manifest(path, write=args.write) for path in manifest_paths]
    if len(results) == 1:
        payload = dict(results[0])
        payload['results'] = results
        payload['inspected_count'] = 1
        _emit(payload, args.json)
        return 1 if payload.get('state') == 'incomplete-evidence' else 0

    payload = _aggregate_scan_payload(scan_root, results)
    _emit(payload, args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
