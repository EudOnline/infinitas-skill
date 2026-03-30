#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.release.state import parse_release_check_state_args, run_release_check_state


def parse_args(argv=None):
    return parse_release_check_state_args(argv)


def main(argv=None):
    args = parse_args(argv)
    return run_release_check_state(
        args.skill,
        mode=args.mode,
        as_json=args.json,
        debug_policy=args.debug_policy,
    )


if __name__ == '__main__':
    raise SystemExit(main())
