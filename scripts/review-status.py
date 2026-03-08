#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY = json.loads((ROOT / 'policy' / 'promotion-policy.json').read_text(encoding='utf-8'))


def resolve_skill(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir() and (p / '_meta.json').exists():
        return p.resolve()
    for stage in ['incubating', 'active', 'archived']:
        q = ROOT / 'skills' / stage / arg
        if q.is_dir() and (q / '_meta.json').exists():
            return q
    raise SystemExit(f'cannot resolve skill: {arg}')


def latest_by_reviewer(entries):
    latest = {}
    for e in entries:
        reviewer = e.get('reviewer')
        if reviewer:
            latest[reviewer] = e
    return latest


def required_approvals(meta):
    reviews = POLICY.get('reviews', {})
    req = reviews.get('default_min_approvals', 0)
    req = reviews.get('risk_overrides', {}).get(meta.get('risk_level'), req)
    return req


def main():
    if len(sys.argv) < 2:
        print('usage: scripts/review-status.py <skill-name-or-path> [--require-pass]', file=sys.stderr)
        return 1
    require_pass = '--require-pass' in sys.argv[2:]
    skill_dir = resolve_skill(sys.argv[1])
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    reviews_path = skill_dir / 'reviews.json'
    reviews = {'entries': []}
    if reviews_path.exists():
        reviews = json.loads(reviews_path.read_text(encoding='utf-8'))
    latest = latest_by_reviewer(reviews.get('entries', []) or [])
    owner = meta.get('owner')
    approvals = [e for r, e in latest.items() if e.get('decision') == 'approved' and r != owner]
    rejections = [e for e in latest.values() if e.get('decision') == 'rejected']
    req = required_approvals(meta)
    print(f"skill: {meta.get('name')}@{meta.get('version')}")
    print(f"risk: {meta.get('risk_level')}")
    print(f"owner: {owner}")
    print(f"required_approvals: {req}")
    print(f"approval_count: {len(approvals)}")
    print(f"rejection_count: {len(rejections)}")
    for reviewer, entry in sorted(latest.items()):
        print(f"- {reviewer}: {entry.get('decision')} ({entry.get('at')})")
    ok = len(approvals) >= req
    if POLICY.get('reviews', {}).get('block_on_rejection', False) and rejections:
        ok = False
    if require_pass and not ok:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
