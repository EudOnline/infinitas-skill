#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY = json.loads((ROOT / 'policy' / 'promotion-policy.json').read_text(encoding='utf-8'))


def latest_reviews(entries):
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


def check_skill(skill_dir: Path, as_active: bool = False) -> int:
    errors = 0
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    stage = 'active' if as_active else skill_dir.parent.name
    if stage != 'active':
        print(f'OK: policy skipped for non-active skill {skill_dir}')
        return 0

    req = POLICY['active_requires']
    reviews_cfg = POLICY.get('reviews', {})
    reviews_path = skill_dir / 'reviews.json'
    reviews = {'entries': []}
    if reviews_path.exists():
        reviews = json.loads(reviews_path.read_text(encoding='utf-8'))
    latest = latest_reviews(reviews.get('entries', []) or [])
    owner = meta.get('owner')
    approvals = []
    rejections = []
    for reviewer, entry in latest.items():
        if entry.get('decision') == 'approved' and (not reviews_cfg.get('reviewer_must_differ_from_owner') or reviewer != owner):
            approvals.append(entry)
        if entry.get('decision') == 'rejected':
            rejections.append(entry)

    if reviews_cfg.get('require_reviews_file') and not reviews_path.is_file():
        print(f'FAIL: {skill_dir}: active skill requires reviews.json', file=sys.stderr)
        errors += 1
    if len(approvals) < required_approvals(meta):
        print(f'FAIL: {skill_dir}: active skill requires at least {required_approvals(meta)} distinct approval(s)', file=sys.stderr)
        errors += 1
    if reviews_cfg.get('block_on_rejection', False) and rejections:
        print(f'FAIL: {skill_dir}: active skill has blocking rejection(s)', file=sys.stderr)
        errors += 1

    if meta.get('review_state') not in req['review_state']:
        print(f'FAIL: {skill_dir}: review_state must be one of {req["review_state"]}', file=sys.stderr)
        errors += 1
    if req.get('require_changelog') and not (skill_dir / 'CHANGELOG.md').is_file():
        print(f'FAIL: {skill_dir}: active skill requires CHANGELOG.md', file=sys.stderr)
        errors += 1
    if req.get('require_smoke_test'):
        smoke = meta.get('tests', {}).get('smoke', 'tests/smoke.md')
        if not (skill_dir / smoke).is_file():
            print(f'FAIL: {skill_dir}: active skill requires smoke test {smoke}', file=sys.stderr)
            errors += 1
    if req.get('require_owner') and not meta.get('owner'):
        print(f'FAIL: {skill_dir}: active skill requires owner', file=sys.stderr)
        errors += 1

    if meta.get('risk_level') == 'high':
        high = POLICY['high_risk_active_requires']
        maintainers = meta.get('maintainers', []) or []
        if len(maintainers) < high.get('min_maintainers', 0):
            print(f'FAIL: {skill_dir}: high-risk active skill requires at least {high.get("min_maintainers", 0)} maintainer(s)', file=sys.stderr)
            errors += 1
        if high.get('require_requires_block') and not isinstance(meta.get('requires'), dict):
            print(f'FAIL: {skill_dir}: high-risk active skill requires a requires block', file=sys.stderr)
            errors += 1

    if errors == 0:
        print(f'OK: promotion policy passed for {skill_dir}')
    return errors


def main():
    args = sys.argv[1:]
    as_active = False
    if '--as-active' in args:
        args.remove('--as-active')
        as_active = True
    targets = [Path(p).resolve() for p in args]
    if not targets:
        base = ROOT / 'skills' / 'active'
        targets = [p for p in base.iterdir() if p.is_dir() and (p / '_meta.json').exists()] if base.exists() else []
    errors = 0
    for target in targets:
        errors += check_skill(target, as_active=as_active)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
