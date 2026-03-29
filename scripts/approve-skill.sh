#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"

python3 - "$ROOT" "$@" <<'PY'
import sys
from pathlib import Path

from review_lib import ALLOWED_DECISIONS, record_review_decision, resolve_skill


def main() -> int:
    if len(sys.argv) < 3:
        print(
            'usage: scripts/approve-skill.sh <skill-name-or-path> --reviewer NAME --decision approved|rejected [--note NOTE]',
            file=sys.stderr,
        )
        return 1

    root = Path(sys.argv[1]).resolve()
    skill_arg = sys.argv[2]
    reviewer = ''
    decision = ''
    note = ''
    index = 3
    while index < len(sys.argv):
        arg = sys.argv[index]
        if arg == '--reviewer':
            if index + 1 >= len(sys.argv):
                print('--reviewer requires a value', file=sys.stderr)
                return 1
            reviewer = sys.argv[index + 1].strip()
            index += 2
            continue
        if arg == '--decision':
            if index + 1 >= len(sys.argv):
                print('--decision requires a value', file=sys.stderr)
                return 1
            decision = sys.argv[index + 1].strip().lower()
            index += 2
            continue
        if arg == '--note':
            if index + 1 >= len(sys.argv):
                print('--note requires a value', file=sys.stderr)
                return 1
            note = sys.argv[index + 1]
            index += 2
            continue
        print(f'unknown argument: {arg}', file=sys.stderr)
        return 1

    if not reviewer:
        print('--reviewer is required', file=sys.stderr)
        return 1
    if decision not in ALLOWED_DECISIONS:
        print(f'--decision must be one of: {", ".join(sorted(ALLOWED_DECISIONS))}', file=sys.stderr)
        return 1

    skill_dir = resolve_skill(root, skill_arg)
    record_review_decision(skill_dir, reviewer=reviewer, decision=decision, note=note, root=root)
    return 0


raise SystemExit(main())
PY
