#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.install.planning import parse_resolve_install_plan_args, run_resolve_install_plan


def parse_args(argv=None):
    return parse_resolve_install_plan_args(argv)


def main(argv=None):
    args = parse_args(argv)
    return run_resolve_install_plan(
        skill_dir=args.skill_dir,
        target_dir=args.target_dir,
        source_registry=args.source_registry,
        source_json=args.source_json,
        mode=args.mode,
        as_json=args.json,
    )


if __name__ == '__main__':
    raise SystemExit(main())
