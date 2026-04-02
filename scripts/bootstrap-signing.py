#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.release.signing_bootstrap_cli import signing_bootstrap_cli_main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(signing_bootstrap_cli_main())
