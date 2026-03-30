#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.policy.cli import build_check_policy_packs_parser, run_check_policy_packs


def main(argv=None):
    parser = build_check_policy_packs_parser(prog='check-policy-packs.py')
    parser.parse_args(argv)
    return run_check_policy_packs(root=ROOT)


if __name__ == '__main__':
    raise SystemExit(main())
