#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.policy.review_commands import recommend_reviewers_main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(recommend_reviewers_main())
