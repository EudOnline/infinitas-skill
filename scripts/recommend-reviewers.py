#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from reviewer_rotation_lib import recommend_reviewers, render_reviewer_recommendations
from review_lib import ReviewPolicyError, resolve_skill

ROOT = Path(__file__).resolve().parent.parent


def parse_args():
    parser = argparse.ArgumentParser(description='Recommend reviewers and escalation paths for one skill')
    parser.add_argument('skill')
    parser.add_argument('--as-active', action='store_true')
    parser.add_argument('--stage')
    parser.add_argument('--json', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    if args.as_active and args.stage:
        print('--as-active and --stage cannot be combined', file=sys.stderr)
        return 1

    skill_dir = resolve_skill(ROOT, args.skill)
    try:
        payload = recommend_reviewers(skill_dir, root=ROOT, stage=args.stage, as_active=args.as_active)
    except ReviewPolicyError as exc:
        for error in exc.errors:
            print(f'FAIL: {error}', file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_reviewer_recommendations(payload))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
