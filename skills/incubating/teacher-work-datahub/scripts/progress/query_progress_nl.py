#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
TARGET = WORKSPACE_ROOT / "skills" / "teacher-work-datahub" / "scripts" / "query" / "query_progress_nl_datahub.py"


def main() -> int:
    cmd = [sys.executable, str(TARGET), *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    raise SystemExit(main())
