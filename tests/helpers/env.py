from __future__ import annotations

import os
from pathlib import Path

from infinitas_skill.testing.env import build_regression_test_env

ROOT = Path(__file__).resolve().parents[2]


def make_test_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    return build_regression_test_env(ROOT, extra=extra, env=os.environ.copy())
