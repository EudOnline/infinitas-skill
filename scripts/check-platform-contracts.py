#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.compatibility.checks import parse_platform_contracts_args, run_check_platform_contracts


def parse_args(argv=None):
    return parse_platform_contracts_args(argv)


def main(argv=None):
    args = parse_args(argv)
    return run_check_platform_contracts(
        max_age_days=args.max_age_days,
        stale_policy=args.stale_policy,
    )


if __name__ == '__main__':
    raise SystemExit(main())
