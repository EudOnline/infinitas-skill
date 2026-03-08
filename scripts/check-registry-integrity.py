#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*(?:@\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?)?$')


def load_skills():
    items = []
    for stage in ['incubating', 'active', 'archived', 'templates']:
        base = ROOT / ('skills' if stage != 'templates' else 'templates') / ('' if stage == 'templates' else stage)
        if stage == 'templates':
            base = ROOT / 'templates'
        if not base.exists():
            continue
        for d in sorted(p for p in base.iterdir() if p.is_dir() and (p / '_meta.json').exists()):
            meta = json.loads((d / '_meta.json').read_text(encoding='utf-8'))
            items.append((stage, d, meta))
    return items


def ref_matches(ref, name, version):
    if '@' in ref:
        rn, rv = ref.split('@', 1)
        return rn == name and rv == version
    return ref == name


def main():
    items = load_skills()
    errors = 0
    names = {(meta.get('name'), meta.get('version'), stage, str(d)): meta for stage, d, meta in items}
    all_refs = []
    active_installable = []
    for stage, d, meta in items:
        for field in ['depends_on', 'conflicts_with']:
            vals = meta.get(field, [])
            if vals is None:
                continue
            if not isinstance(vals, list) or not all(isinstance(x, str) for x in vals):
                print(f'FAIL: {d}: {field} must be an array of strings', file=sys.stderr)
                errors += 1
                continue
            for ref in vals:
                if not REF_RE.match(ref):
                    print(f'FAIL: {d}: invalid {field} ref {ref!r}', file=sys.stderr)
                    errors += 1
                all_refs.append((field, ref, stage, d, meta))
        if stage == 'active' and meta.get('distribution', {}).get('installable', True):
            active_installable.append((d, meta))

    for field, ref, stage, d, meta in all_refs:
        if ref == meta.get('name') or ref == f"{meta.get('name')}@{meta.get('version')}":
            print(f'FAIL: {d}: {field} cannot reference itself ({ref})', file=sys.stderr)
            errors += 1
            continue
        if stage == 'active' and field == 'depends_on':
            matched = False
            for other_stage, other_dir, other_meta in items:
                if other_stage not in {'active', 'archived'}:
                    continue
                if ref_matches(ref, other_meta.get('name'), other_meta.get('version')):
                    matched = True
                    break
                if other_meta.get('snapshot_of') == ref:
                    matched = True
                    break
            if not matched:
                print(f'FAIL: {d}: unresolved active dependency {ref}', file=sys.stderr)
                errors += 1

    # detect active/installable conflict pairs
    active_names = {meta.get('name'): (d, meta) for d, meta in active_installable}
    for d, meta in active_installable:
        for ref in meta.get('conflicts_with', []) or []:
            name = ref.split('@', 1)[0]
            if name in active_names:
                other_d, other_meta = active_names[name]
                print(f'WARN: {meta.get("name")} conflicts with active skill {other_meta.get("name")} ({other_d})', file=sys.stderr)

    if errors:
        print(f'Integrity check failed with {errors} error(s).', file=sys.stderr)
        return 1
    print(f'OK: registry integrity checked across {len(items)} skill directories')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
