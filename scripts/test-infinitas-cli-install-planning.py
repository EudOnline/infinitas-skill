#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    from tests.integration.test_cli_install_planning import (
        main as run_focused_install_planning_checks,
    )

    try:
        run_focused_install_planning_checks()
    except AssertionError as exc:
        fail(str(exc))
    print("OK: infinitas install planning CLI mirrors legacy script output")


if __name__ == "__main__":
    main()
