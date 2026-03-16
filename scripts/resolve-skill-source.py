#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from distribution_lib import load_distribution_index
from http_registry_lib import HostedRegistryError, fetch_json, registry_catalog_path
from registry_source_lib import (
    apply_registry_federation,
    load_registry_config,
    normalized_auth,
    registry_identity,
    registry_is_resolution_candidate,
    resolve_registry_root,
)
from skill_identity_lib import normalize_skill_identity, parse_requested_skill

ROOT = Path(__file__).resolve().parent.parent


def expected_skill_tag(name, version):
    if not name or not version:
        return None
    return f'skill/{name}/v{version}'


def append_registry_item(reg, items, payload):
    resolved = apply_registry_federation(reg, payload)
    if resolved is not None:
        items.append(resolved)


def scan_registry(reg):
    if reg.get('kind') == 'http':
        return scan_http_registry(reg)
    reg_root = resolve_registry_root(ROOT, reg)
    if reg_root is None or not reg_root.exists():
        return []
    reg_info = registry_identity(ROOT, reg)
    distribution_index = load_distribution_index(reg_root)
    distribution_by_identity = {
        (entry.get('qualified_name') or entry.get('name'), entry.get('version')): entry for entry in distribution_index
    }
    matched_distribution = set()
    items = []
    skills_root = reg_root / 'skills'
    for stage in ['active', 'incubating', 'archived']:
        stage_dir = skills_root / stage
        if not stage_dir.exists():
            continue
        for d in sorted(p for p in stage_dir.iterdir() if p.is_dir() and (p / '_meta.json').exists()):
            try:
                meta = json.loads((d / '_meta.json').read_text(encoding='utf-8'))
            except Exception:
                continue
            identity = normalize_skill_identity(meta)
            distribution = distribution_by_identity.get((identity.get('qualified_name') or meta.get('name'), meta.get('version')))
            append_registry_item(reg, items, {
                **reg_info,
                'stage': distribution.get('status') if distribution else stage,
                'path': str((reg_root / distribution.get('manifest_path')).resolve()) if distribution else str(d),
                'skill_path': str(d),
                'relative_path': distribution.get('manifest_path') if distribution else str(d.relative_to(reg_root)),
                'dir_name': d.name,
                'name': meta.get('name'),
                'publisher': identity.get('publisher'),
                'qualified_name': identity.get('qualified_name'),
                'identity_mode': identity.get('identity_mode'),
                'version': meta.get('version'),
                'status': meta.get('status'),
                'snapshot_of': meta.get('snapshot_of'),
                'snapshot_created_at': meta.get('snapshot_created_at'),
                'snapshot_label': meta.get('snapshot_label'),
                'installable': bool(meta.get('distribution', {}).get('installable', True)),
                'expected_tag': distribution.get('source_snapshot_tag') if distribution else expected_skill_tag(meta.get('name'), meta.get('version')),
                'source_type': 'distribution-manifest' if distribution else 'working-tree',
                'distribution_manifest': distribution.get('manifest_path') if distribution else None,
                'distribution_bundle': distribution.get('bundle_path') if distribution else None,
                'distribution_bundle_sha256': distribution.get('bundle_sha256') if distribution else None,
                'distribution_attestation': distribution.get('attestation_path') if distribution else None,
                'distribution_attestation_signature': distribution.get('attestation_signature_path') if distribution else None,
                'source_snapshot_kind': distribution.get('source_snapshot_kind') if distribution else None,
                'source_snapshot_tag': distribution.get('source_snapshot_tag') if distribution else None,
                'source_snapshot_ref': distribution.get('source_snapshot_ref') if distribution else None,
                'source_snapshot_commit': distribution.get('source_snapshot_commit') if distribution else None,
                'registry_commit': distribution.get('source_snapshot_commit') if distribution else reg_info.get('registry_commit'),
                'registry_tag': distribution.get('source_snapshot_tag') if distribution else reg_info.get('registry_tag'),
                'registry_ref': distribution.get('source_snapshot_ref') if distribution else reg_info.get('registry_ref'),
            })
            if distribution:
                matched_distribution.add((identity.get('qualified_name') or meta.get('name'), meta.get('version')))

    for distribution in distribution_index:
        key = (distribution.get('qualified_name') or distribution.get('name'), distribution.get('version'))
        if key in matched_distribution:
            continue
        append_registry_item(reg, items, {
            **reg_info,
            'stage': distribution.get('status') or 'archived',
            'path': str((reg_root / distribution.get('manifest_path')).resolve()),
            'skill_path': None,
            'relative_path': distribution.get('manifest_path'),
            'dir_name': Path(distribution.get('manifest_path') or '').parent.name,
            'name': distribution.get('name'),
            'publisher': distribution.get('publisher'),
            'qualified_name': distribution.get('qualified_name'),
            'identity_mode': distribution.get('identity_mode'),
            'version': distribution.get('version'),
            'status': distribution.get('status'),
            'snapshot_of': None,
            'snapshot_created_at': distribution.get('generated_at'),
            'snapshot_label': None,
            'installable': True,
            'expected_tag': distribution.get('source_snapshot_tag') or expected_skill_tag(distribution.get('name'), distribution.get('version')),
            'source_type': 'distribution-manifest',
            'distribution_manifest': distribution.get('manifest_path'),
            'distribution_bundle': distribution.get('bundle_path'),
            'distribution_bundle_sha256': distribution.get('bundle_sha256'),
            'distribution_attestation': distribution.get('attestation_path'),
            'distribution_attestation_signature': distribution.get('attestation_signature_path'),
            'source_snapshot_kind': distribution.get('source_snapshot_kind'),
            'source_snapshot_tag': distribution.get('source_snapshot_tag'),
            'source_snapshot_ref': distribution.get('source_snapshot_ref'),
            'source_snapshot_commit': distribution.get('source_snapshot_commit'),
            'registry_commit': distribution.get('source_snapshot_commit') or reg_info.get('registry_commit'),
            'registry_tag': distribution.get('source_snapshot_tag') or reg_info.get('registry_tag'),
            'registry_ref': distribution.get('source_snapshot_ref') or reg_info.get('registry_ref'),
        })
    return items


def scan_http_registry(reg):
    reg_info = registry_identity(ROOT, reg)
    auth = normalized_auth(reg)
    try:
        payload = fetch_json(
            reg.get('base_url'),
            registry_catalog_path(reg, 'ai_index'),
            token_env=auth.get('env') if auth.get('mode') == 'token' else None,
        )
    except HostedRegistryError:
        return []

    items = []
    for skill in payload.get('skills') or []:
        if not isinstance(skill, dict):
            continue
        name = skill.get('name')
        qualified_name = skill.get('qualified_name') or name
        publisher = skill.get('publisher')
        versions = skill.get('versions') or {}
        default_version = skill.get('default_install_version') or skill.get('latest_version')
        for version, version_info in versions.items():
            if not isinstance(version_info, dict):
                continue
            stage = 'active' if version == default_version else 'archived'
            append_registry_item(
                reg,
                items,
                {
                    **reg_info,
                    'stage': stage,
                    'path': version_info.get('manifest_path'),
                    'skill_path': None,
                    'relative_path': version_info.get('manifest_path'),
                    'dir_name': name,
                    'name': name,
                    'publisher': publisher,
                    'qualified_name': qualified_name,
                    'identity_mode': skill.get('identity_mode'),
                    'version': version,
                    'status': stage,
                    'snapshot_of': None,
                    'snapshot_created_at': version_info.get('published_at'),
                    'snapshot_label': None,
                    'installable': bool(version_info.get('installable', True)),
                    'expected_tag': expected_skill_tag(name, version),
                    'source_type': 'distribution-manifest',
                    'distribution_manifest': version_info.get('manifest_path'),
                    'distribution_bundle': version_info.get('bundle_path'),
                    'distribution_bundle_sha256': version_info.get('bundle_sha256'),
                    'distribution_attestation': version_info.get('attestation_path'),
                    'distribution_attestation_signature': version_info.get('attestation_signature_path'),
                    'source_snapshot_kind': None,
                    'source_snapshot_tag': None,
                    'source_snapshot_ref': None,
                    'source_snapshot_commit': None,
                    'registry_commit': None,
                    'registry_tag': None,
                    'registry_ref': None,
                },
            )
    return items


def load_candidates(registry=None):
    cfg = load_registry_config(ROOT)
    items = []
    explicit_registry = bool(registry)
    for reg in cfg.get('registries', []):
        if not reg.get('enabled', True):
            continue
        if registry and reg.get('name') != registry:
            continue
        if not registry_is_resolution_candidate(reg, explicit_registry=explicit_registry):
            continue
        items.extend(scan_registry(reg))
    return items


def sort_key(item):
    stage_order = {'active': 0, 'incubating': 1, 'archived': 2}
    return (
        -int(item.get('registry_priority', 0)),
        0 if item.get('source_type') == 'distribution-manifest' else 1,
        stage_order.get(item['stage'], 9),
        item.get('snapshot_created_at') or '',
        item['dir_name'],
    )


def archived_snapshot_sort_key(item):
    ts = item.get('snapshot_created_at') or ''
    ts_num = int(ts.replace('T', '').replace('Z', '').replace('-', '').replace(':', '')) if ts else 0
    return (-int(item.get('registry_priority', 0)), 0 if item.get('source_type') == 'distribution-manifest' else 1, -ts_num, item['dir_name'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--version')
    ap.add_argument('--allow-incubating', action='store_true')
    ap.add_argument('--registry')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    requested_publisher, requested_name = parse_requested_skill(args.name)
    candidates = []
    for item in load_candidates(args.registry):
        if requested_publisher:
            if item.get('qualified_name') == args.name:
                candidates.append(item)
        elif item.get('name') == requested_name:
            candidates.append(item)
    if not args.allow_incubating:
        candidates = [x for x in candidates if x['stage'] != 'incubating']

    resolved = None
    reason = None

    if args.version:
        exact = [x for x in candidates if x.get('version') == args.version]
        snapshot_refs = [f"{requested_name}@{args.version}"]
        if requested_publisher:
            snapshot_refs.insert(0, f"{args.name}@{args.version}")
        archived_snapshots = [x for x in exact if x['stage'] == 'archived' and x.get('snapshot_of') in snapshot_refs]
        if archived_snapshots:
            archived_snapshots.sort(key=archived_snapshot_sort_key)
            resolved = archived_snapshots[0]
            reason = 'archived-exact-snapshot'
        elif exact:
            exact.sort(key=sort_key)
            resolved = exact[0]
            reason = 'exact-version'
    else:
        active = [x for x in candidates if x['stage'] == 'active']
        if active:
            active.sort(key=sort_key)
            resolved = active[0]
            reason = 'active-default'

    if resolved is None:
        suffix = f' from registry {args.registry}' if args.registry else ''
        raise SystemExit(f'No matching skill source found for {args.name}{"@" + args.version if args.version else ""}{suffix}.')

    resolved = dict(resolved)
    if resolved.get('source_type') == 'distribution-manifest':
        if reason == 'active-default':
            reason = 'distribution-active-default'
        elif reason == 'exact-version':
            reason = 'distribution-exact-version'
        elif reason == 'archived-exact-snapshot':
            reason = 'distribution-archived-exact-version'
    resolved['resolution_reason'] = reason
    if args.json:
        print(json.dumps(resolved, ensure_ascii=False, indent=2))
    else:
        print(resolved['path'])


if __name__ == '__main__':
    main()
