#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"

python3 - "$ROOT" "$@" <<'PY'
import sys
from pathlib import Path

from review_lib import request_review, resolve_skill


def main() -> int:
    if len(sys.argv) < 3:
        print('usage: scripts/request-review.sh <skill-name-or-path> [--note NOTE]', file=sys.stderr)
        return 1

    root = Path(sys.argv[1]).resolve()
    skill_arg = sys.argv[2]
    note = ''
    index = 3
    while index < len(sys.argv):
        arg = sys.argv[index]
        if arg == '--note':
            if index + 1 >= len(sys.argv):
                print('--note requires a value', file=sys.stderr)
                return 1
            note = sys.argv[index + 1]
            index += 2
            continue
        print(f'unknown argument: {arg}', file=sys.stderr)
        return 1

    skill_dir = resolve_skill(root, skill_arg)
    request_review(skill_dir, note=note, root=root)
    return 0


raise SystemExit(main())
PY
