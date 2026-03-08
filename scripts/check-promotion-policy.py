#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from review_lib import ReviewPolicyError, evaluate_review_state, load_promotion_policy


def check_skill(skill_dir: Path, as_active: bool = False) -> int:
    errors = 0
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    stage = 'active' if as_active else skill_dir.parent.name
    if stage != 'active':
        print(f'OK: policy skipped for non-active skill {skill_dir}')
        return 0

    policy = load_promotion_policy(ROOT)
    req = policy['active_requires']
    reviews_cfg = policy.get('reviews', {})
    evaluation = evaluate_review_state(skill_dir, root=ROOT, stage='active', policy=policy)
    reviews_path = skill_dir / 'reviews.json'

    if reviews_cfg.get('require_reviews_file') and not reviews_path.is_file():
        print(f'FAIL: {skill_dir}: active skill requires reviews.json', file=sys.stderr)
        errors += 1
    if evaluation['approval_count'] < evaluation['required_approvals']:
        print(f'FAIL: {skill_dir}: active skill requires at least {evaluation["required_approvals"]} counted approval(s)', file=sys.stderr)
        errors += 1
    if evaluation['missing_groups']:
        print(f'FAIL: {skill_dir}: active skill is missing reviewer group coverage for {", ".join(evaluation["missing_groups"])}', file=sys.stderr)
        errors += 1
    if reviews_cfg.get('block_on_rejection', False) and evaluation['blocking_rejection_count']:
        print(f'FAIL: {skill_dir}: active skill has blocking rejection(s)', file=sys.stderr)
        errors += 1
    if not evaluation['review_gate_pass'] and errors == 0:
        print(f'FAIL: {skill_dir}: active skill does not satisfy computed review quorum', file=sys.stderr)
        errors += 1

    if evaluation['effective_review_state'] not in req['review_state']:
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
    try:
        load_promotion_policy(ROOT)
    except ReviewPolicyError as exc:
        for error in exc.errors:
            print(f'FAIL: {error}', file=sys.stderr)
        raise SystemExit(1)
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
