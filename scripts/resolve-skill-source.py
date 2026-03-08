#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def resolve_registry_root(reg):
    local_path = reg.get('local_path')
    if not local_path:
        return ROOT if reg.get('name') == 'self' else None
    p = Path(local_path)
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    return p


def load_registry_config():
    return json.loads((ROOT / 'config' / 'registry-sources.json').read_text(encoding='utf-8'))


def scan_registry(reg):
    reg_root = resolve_registry_root(reg)
    if reg_root is None or not reg_root.exists():
        return []
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
                'registry_name': reg.get('name'),
                'registry_kind': reg.get('kind'),
                'registry_url': reg.get('url'),
                'registry_priority': reg.get('priority', 0),
                'registry_trust': reg.get('trust'),
                'registry_root': str(reg_root),
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
            })
    return items


def load_candidates(registry=None):
    cfg = load_registry_config()
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
        archived_snapshots.sort(key=lambda x: (-int(x.get('registry_priority', 0)), x.get('snapshot_created_at') or '', x['dir_name']), reverse=False)
        if archived_snapshots:
            archived_snapshots.sort(key=lambda x: (-int(x.get('registry_priority', 0)), -(int(x.get('snapshot_created_at', '0').replace('T','').replace('Z','').replace('-','').replace(':','')) if x.get('snapshot_created_at') else 0), x['dir_name']))
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
        print(f'No matching skill source found for {args.name}{"@" + args.version if args.version else ""}{suffix}.', file=sys.stderr)
        return 1

    resolved = dict(resolved)
    resolved['resolution_reason'] = reason
    if args.json:
        print(json.dumps(resolved, ensure_ascii=False, indent=2))
    else:
        print(resolved['path'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
