from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.testing.env import build_regression_test_env


def make_test_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    return build_regression_test_env(ROOT, extra=extra, env=os.environ.copy())
