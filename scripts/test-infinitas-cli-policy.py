#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers.cli_policy import main as run_checks


def main():
    try:
        run_checks()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("OK: infinitas policy CLI mirrors legacy policy scripts")


if __name__ == "__main__":
    main()
