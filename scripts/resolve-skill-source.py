#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_candidates():
    items = []
    for stage in ['active', 'incubating', 'archived']:
        stage_dir = ROOT / 'skills' / stage
        if not stage_dir.exists():
            continue
        for d in sorted(p for p in stage_dir.iterdir() if p.is_dir() and (p / '_meta.json').exists()):
            try:
                meta = json.loads((d / '_meta.json').read_text(encoding='utf-8'))
            except Exception:
                continue
            items.append({
                'stage': stage,
                'path': str(d),
                'relative_path': str(d.relative_to(ROOT)),
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


def sort_key(item):
    stage_order = {'active': 0, 'incubating': 1, 'archived': 2}
    return (
        stage_order.get(item['stage'], 9),
        item.get('snapshot_created_at') or '',
        item['dir_name'],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--version')
    ap.add_argument('--allow-incubating', action='store_true')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    candidates = [x for x in load_candidates() if x.get('name') == args.name]
    if not args.allow_incubating:
        candidates = [x for x in candidates if x['stage'] != 'incubating']

    resolved = None
    reason = None

    if args.version:
        exact = [x for x in candidates if x.get('version') == args.version]
        archived_snapshots = [x for x in exact if x['stage'] == 'archived' and x.get('snapshot_of') == f"{args.name}@{args.version}"]
        archived_snapshots.sort(key=lambda x: (x.get('snapshot_created_at') or '', x['dir_name']), reverse=True)
        if archived_snapshots:
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
        print(f'No matching skill source found for {args.name}{"@" + args.version if args.version else ""}.', file=sys.stderr)
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
