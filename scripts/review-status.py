#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from reviewer_rotation_lib import recommend_reviewers, render_reviewer_recommendations
from review_lib import ReviewPolicyError, evaluate_review_state, resolve_skill


def print_csv_list(name, values):
    print(f"{name}: {', '.join(values) if values else '-'}")


def main():
    if len(sys.argv) < 2:
        print('usage: scripts/review-status.py <skill-name-or-path> [--require-pass] [--as-active] [--stage STAGE] [--json] [--show-recommendations]', file=sys.stderr)
        return 1
    args = sys.argv[2:]
    require_pass = False
    as_active = False
    as_json = False
    show_recommendations = False
    stage = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == '--require-pass':
            require_pass = True
            index += 1
            continue
        if arg == '--as-active':
            as_active = True
            index += 1
            continue
        if arg == '--json':
            as_json = True
            index += 1
            continue
        if arg == '--show-recommendations':
            show_recommendations = True
            index += 1
            continue
        if arg == '--stage':
            stage = args[index + 1] if index + 1 < len(args) else None
            if stage is None:
                print('--stage requires a value', file=sys.stderr)
                return 1
            index += 2
            continue
        print(f'unknown argument: {arg}', file=sys.stderr)
        return 1

    if as_active and stage is not None:
        print('--as-active and --stage cannot be combined', file=sys.stderr)
        return 1

    skill_dir = resolve_skill(ROOT, sys.argv[1])
    try:
        evaluation = evaluate_review_state(skill_dir, root=ROOT, stage=stage, as_active=as_active)
        recommendations = recommend_reviewers(skill_dir, root=ROOT, stage=stage, as_active=as_active) if show_recommendations else None
    except ReviewPolicyError as exc:
        for error in exc.errors:
            print(f'FAIL: {error}', file=sys.stderr)
        return 1

    if as_json:
        payload = dict(evaluation)
        if recommendations is not None:
            payload['recommendations'] = recommendations
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if require_pass and not evaluation['review_gate_pass']:
            return 1
        return 0

    print(f"skill: {evaluation['skill']}@{evaluation['version']}")
    print(f"actual_stage: {evaluation['actual_stage']}")
    print(f"evaluated_stage: {evaluation['evaluated_stage']}")
    print(f"risk: {evaluation['risk_level']}")
    print(f"owner: {evaluation['owner']}")
    print(f"declared_review_state: {evaluation['declared_review_state']}")
    print(f"effective_review_state: {evaluation['effective_review_state']}")
    print(f"review_requests: {evaluation['review_request_count']}")
    print(f"required_approvals: {evaluation['required_approvals']}")
    print(f"approval_count: {evaluation['approval_count']}")
    print(f"rejection_count: {evaluation['rejection_count']}")
    print(f"blocking_rejections: {evaluation['blocking_rejection_count']}")
    print(f"quorum_met: {'yes' if evaluation['quorum_met'] else 'no'}")
    print(f"review_gate_pass: {'yes' if evaluation['review_gate_pass'] else 'no'}")
    print_csv_list('required_groups', evaluation['required_groups'])
    print_csv_list('covered_groups', evaluation['covered_groups'])
    print_csv_list('missing_groups', evaluation['missing_groups'])
    print(f"ignored_decisions: {len(evaluation['ignored_decisions'])}")
    if evaluation['latest_decisions']:
        print('latest_decisions:')
        for item in evaluation['latest_decisions']:
            reasons = f" [{'; '.join(item['reasons'])}]" if item['reasons'] else ''
            groups = ','.join(item['groups']) if item['groups'] else '-'
            counted = 'yes' if item['counted'] else 'no'
            print(f"- {item['reviewer']}: {item['decision']} counted={counted} groups={groups} at={item['at']}{reasons}")
    if recommendations is not None:
        print(render_reviewer_recommendations(recommendations))
    if require_pass and not evaluation['review_gate_pass']:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
