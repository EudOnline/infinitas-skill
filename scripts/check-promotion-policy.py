#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.policy.cli import build_check_promotion_parser, run_check_promotion


def main(argv=None):
    parser = build_check_promotion_parser(prog='check-promotion-policy.py')
    args = parser.parse_args(argv)
    return run_check_promotion(
        targets=args.targets,
        as_active=args.as_active,
        as_json=args.json,
        debug_policy=args.debug_policy,
        root=ROOT,
    )


if __name__ == '__main__':
    raise SystemExit(main())
