#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from registry_source_lib import load_registry_config, registry_identity, resolve_registry_root

ROOT = Path(__file__).resolve().parent.parent


def expected_skill_tag(name, version):
    if not name or not version:
        return None
    return f'skill/{name}/v{version}'


def scan_registry(reg):
    reg_root = resolve_registry_root(ROOT, reg)
    if reg_root is None or not reg_root.exists():
        return []
    reg_info = registry_identity(ROOT, reg)
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
            items.append({
                **reg_info,
                'stage': stage,
                'path': str(d),
                'relative_path': str(d.relative_to(reg_root)),
                'dir_name': d.name,
                'name': meta.get('name'),
                'version': meta.get('version'),
                'status': meta.get('status'),
                'snapshot_of': meta.get('snapshot_of'),
                'snapshot_created_at': meta.get('snapshot_created_at'),
                'snapshot_label': meta.get('snapshot_label'),
                'installable': bool(meta.get('distribution', {}).get('installable', True)),
                'expected_tag': expected_skill_tag(meta.get('name'), meta.get('version')),
            })
    return items


def load_candidates(registry=None):
    cfg = load_registry_config(ROOT)
    items = []
    for reg in cfg.get('registries', []):
        if not reg.get('enabled', True):
            continue
        if registry and reg.get('name') != registry:
            continue
        items.extend(scan_registry(reg))
    return items


def sort_key(item):
    stage_order = {'active': 0, 'incubating': 1, 'archived': 2}
    return (
        -int(item.get('registry_priority', 0)),
        stage_order.get(item['stage'], 9),
        item.get('snapshot_created_at') or '',
        item['dir_name'],
    )


def archived_snapshot_sort_key(item):
    ts = item.get('snapshot_created_at') or ''
    ts_num = int(ts.replace('T', '').replace('Z', '').replace('-', '').replace(':', '')) if ts else 0
    return (-int(item.get('registry_priority', 0)), -ts_num, item['dir_name'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--version')
    ap.add_argument('--allow-incubating', action='store_true')
    ap.add_argument('--registry')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    candidates = [x for x in load_candidates(args.registry) if x.get('name') == args.name]
    if not args.allow_incubating:
        candidates = [x for x in candidates if x['stage'] != 'incubating']

    resolved = None
    reason = None

    if args.version:
        exact = [x for x in candidates if x.get('version') == args.version]
        archived_snapshots = [x for x in exact if x['stage'] == 'archived' and x.get('snapshot_of') == f"{args.name}@{args.version}"]
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
    resolved['resolution_reason'] = reason
    if args.json:
        print(json.dumps(resolved, ensure_ascii=False, indent=2))
    else:
        print(resolved['path'])


if __name__ == '__main__':
    main()
