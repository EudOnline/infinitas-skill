#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from policy_pack_lib import PolicyPackError, load_policy_domain_resolution
from policy_trace_lib import build_policy_trace, render_policy_trace
from review_lib import ReviewPolicyError, evaluate_review_state, load_promotion_policy


def _rule(message, *, value=None):
    item = {'rule': message}
    if value is not None:
        item['value'] = value
    return item


def collect_skill_report(skill_dir: Path, *, as_active: bool = False, root: Path = ROOT):
    skill_dir = Path(skill_dir).resolve()
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    stage = 'active' if as_active else skill_dir.parent.name

    try:
        policy_resolution = load_policy_domain_resolution(root, 'promotion_policy')
    except PolicyPackError as exc:
        raise ReviewPolicyError(exc.errors) from exc

    policy = policy_resolution['effective']
    reviews_cfg = policy.get('reviews', {})
    req = policy.get('active_requires', {})
    errors = []
    blocking_rules = []
    next_actions = []
    evaluation = None

    if stage != 'active':
        trace = build_policy_trace(
            domain='promotion_policy',
            decision='skipped',
            summary='promotion policy is enforced only for active-stage evaluation',
            effective_sources=policy_resolution.get('effective_sources'),
            applied_rules=[_rule('promotion checks are skipped outside active-stage evaluation')],
            reasons=['use --as-active or run the check against an active skill to enforce promotion policy'],
            next_actions=['rerun with --as-active if you want active-stage gating'],
        )
        return {
            'skill': meta.get('name', skill_dir.name),
            'skill_path': str(skill_dir.relative_to(root)),
            'evaluated_stage': stage,
            'passed': True,
            'error_count': 0,
            'errors': [],
            'evaluation': None,
            'policy_trace': trace,
        }

    evaluation = evaluate_review_state(skill_dir, root=root, stage='active', policy=policy)
    reviews_path = skill_dir / 'reviews.json'

    if reviews_cfg.get('require_reviews_file') and not reviews_path.is_file():
        message = f'{skill_dir}: active skill requires reviews.json'
        errors.append(message)
        blocking_rules.append(_rule('reviews file is required for active skills', value='missing reviews.json'))
        next_actions.append('add reviews.json before promoting this skill')
    if evaluation['approval_count'] < evaluation['required_approvals']:
        message = f'{skill_dir}: active skill requires at least {evaluation["required_approvals"]} counted approval(s)'
        errors.append(message)
        blocking_rules.append(_rule('minimum counted approvals must be met', value=f'{evaluation["approval_count"]}/{evaluation["required_approvals"]}'))
        next_actions.append('collect the required number of counted approvals')
    if evaluation['missing_groups']:
        joined = ', '.join(evaluation['missing_groups'])
        message = f'{skill_dir}: active skill is missing reviewer group coverage for {joined}'
        errors.append(message)
        blocking_rules.append(_rule('required reviewer groups must be covered', value=joined))
        next_actions.append('request review from the missing reviewer groups')
    if reviews_cfg.get('block_on_rejection', False) and evaluation['blocking_rejection_count']:
        message = f'{skill_dir}: active skill has blocking rejection(s)'
        errors.append(message)
        blocking_rules.append(_rule('blocking rejections must be resolved before promotion', value=evaluation['blocking_rejection_count']))
        next_actions.append('resolve or supersede the blocking rejection decisions')
    if not evaluation['review_gate_pass'] and not errors:
        message = f'{skill_dir}: active skill does not satisfy computed review quorum'
        errors.append(message)
        blocking_rules.append(_rule('computed review quorum must pass'))
        next_actions.append('inspect the review quorum inputs and latest decisions')

    if evaluation['effective_review_state'] not in req.get('review_state', []):
        message = f'{skill_dir}: review_state must be one of {req.get("review_state", [])}'
        errors.append(message)
        blocking_rules.append(_rule('effective review_state must be allowed for promotion', value=evaluation['effective_review_state']))
    if req.get('require_changelog') and not (skill_dir / 'CHANGELOG.md').is_file():
        message = f'{skill_dir}: active skill requires CHANGELOG.md'
        errors.append(message)
        blocking_rules.append(_rule('CHANGELOG.md is required for active promotion'))
    if req.get('require_smoke_test'):
        smoke = meta.get('tests', {}).get('smoke', 'tests/smoke.md')
        if not (skill_dir / smoke).is_file():
            message = f'{skill_dir}: active skill requires smoke test {smoke}'
            errors.append(message)
            blocking_rules.append(_rule('smoke test file is required for active promotion', value=smoke))
    if req.get('require_owner') and not meta.get('owner'):
        message = f'{skill_dir}: active skill requires owner'
        errors.append(message)
        blocking_rules.append(_rule('owner metadata is required for active promotion'))

    high = policy.get('high_risk_active_requires', {}) if isinstance(policy.get('high_risk_active_requires'), dict) else {}
    if meta.get('risk_level') == 'high':
        maintainers = meta.get('maintainers', []) or []
        if len(maintainers) < high.get('min_maintainers', 0):
            message = f'{skill_dir}: high-risk active skill requires at least {high.get("min_maintainers", 0)} maintainer(s)'
            errors.append(message)
            blocking_rules.append(_rule('high-risk skills require minimum maintainer coverage', value=f'{len(maintainers)}/{high.get("min_maintainers", 0)}'))
        if high.get('require_requires_block') and not isinstance(meta.get('requires'), dict):
            message = f'{skill_dir}: high-risk active skill requires a requires block'
            errors.append(message)
            blocking_rules.append(_rule('high-risk skills require a requires block'))

    trace = build_policy_trace(
        domain='promotion_policy',
        decision='allow' if not errors else 'deny',
        summary='promotion policy passed for active skill' if not errors else f'promotion policy blocked by {len(errors)} issue(s)',
        effective_sources=policy_resolution.get('effective_sources'),
        applied_rules=[
            _rule('active skill review_state must satisfy active_requires.review_state', value=','.join(req.get('review_state', []))),
            _rule('review quorum is computed from latest distinct reviewer decisions', value='enabled'),
            _rule('required reviewer groups must be covered', value=','.join(evaluation.get('required_groups', [])) or '-'),
            _rule('minimum approvals must be met', value=evaluation.get('required_approvals', 0)),
            _rule('blocking rejections are enforced', value=bool(reviews_cfg.get('block_on_rejection', False))),
        ],
        blocking_rules=blocking_rules,
        reasons=[
            f"effective_review_state={evaluation.get('effective_review_state')}",
            f"approval_count={evaluation.get('approval_count')}",
            f"blocking_rejections={evaluation.get('blocking_rejection_count')}",
        ],
        next_actions=next_actions,
    )
    return {
        'skill': meta.get('name', skill_dir.name),
        'skill_path': str(skill_dir.relative_to(root)),
        'evaluated_stage': stage,
        'passed': not errors,
        'error_count': len(errors),
        'errors': errors,
        'evaluation': evaluation,
        'policy_trace': trace,
    }


def print_text_report(report, *, debug_policy=False):
    if report['errors']:
        for message in report['errors']:
            print(f'FAIL: {message}', file=sys.stderr)
        if debug_policy:
            print(render_policy_trace(report['policy_trace']), file=sys.stderr)
        return
    print(f"OK: promotion policy passed for {ROOT / report['skill_path']}")
    if debug_policy:
        print(render_policy_trace(report['policy_trace']))


def parse_args():
    parser = argparse.ArgumentParser(description='Check active promotion policy for a skill')
    parser.add_argument('targets', nargs='*', help='Skill directory path(s) to check')
    parser.add_argument('--as-active', action='store_true', help='Evaluate targets as active-stage skills')
    parser.add_argument('--json', action='store_true', help='Print machine-readable output')
    parser.add_argument('--debug-policy', action='store_true', help='Print a human-readable policy trace')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        load_promotion_policy(ROOT)
    except ReviewPolicyError as exc:
        for error in exc.errors:
            print(f'FAIL: {error}', file=sys.stderr)
        raise SystemExit(1)

    targets = [Path(p).resolve() for p in args.targets]
    if not targets:
        base = ROOT / 'skills' / 'active'
        targets = [p for p in base.iterdir() if p.is_dir() and (p / '_meta.json').exists()] if base.exists() else []

    reports = [collect_skill_report(target, as_active=args.as_active, root=ROOT) for target in targets]
    error_count = sum(report['error_count'] for report in reports)

    if args.json:
        payload = reports[0] if len(reports) == 1 else {'results': reports, 'error_count': error_count}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            print_text_report(report, debug_policy=args.debug_policy)

    if error_count:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
