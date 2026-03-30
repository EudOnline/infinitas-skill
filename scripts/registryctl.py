#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.registry.cli import registry_main


def main(argv=None):
    return registry_main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
