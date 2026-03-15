#!/usr/bin/env python3
import argparse
import json
import sys

from policy_trace_lib import render_policy_trace
from release_lib import ROOT, collect_release_state, format_release_state, resolve_skill, ReleaseError


def parse_args():
    parser = argparse.ArgumentParser(description='Check stable release invariants for a skill')
    parser.add_argument('skill', help='Skill name or path')
    parser.add_argument(
        '--mode',
        choices=['preflight', 'local-tag', 'stable-release'],
        default='stable-release',
        help='Which release invariant set to enforce',
    )
    parser.add_argument('--json', action='store_true', help='Print machine-readable state')
    parser.add_argument('--debug-policy', action='store_true', help='Print a human-readable policy trace')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        skill_dir = resolve_skill(ROOT, args.skill)
        state = collect_release_state(skill_dir, mode=args.mode)
    except ReleaseError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print(format_release_state(state))
        if args.debug_policy:
            print()
            print(render_policy_trace(state.get('policy_trace') or {}))

    if not state['release_ready']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
