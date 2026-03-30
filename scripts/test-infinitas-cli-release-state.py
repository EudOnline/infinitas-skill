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
    from tests.integration.test_cli_release_state import main as run_focused_release_state_checks

    try:
        run_focused_release_state_checks()
    except AssertionError as exc:
        fail(str(exc))
    print("OK: infinitas release check-state CLI mirrors legacy script output")


if __name__ == "__main__":
    main()
