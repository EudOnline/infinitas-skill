#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PARSER = ROOT / "skills" / "teacher-work-datahub" / "scripts" / "parsers" / "parse_teacher_allocation.py"
CANDIDATES = [
    ROOT / ".venv-schedule" / "bin" / "python",
    ROOT / ".venv" / "bin" / "python",
    Path(sys.executable),
    Path("/usr/bin/python3"),
]


def has_xlrd(python_bin: Path) -> bool:
    if not python_bin.exists():
        return False
    r = subprocess.run([str(python_bin), "-c", "import xlrd"], capture_output=True)
    return r.returncode == 0


def choose_python() -> Path:
    for candidate in CANDIDATES:
        if has_xlrd(candidate):
            return candidate
    raise SystemExit("未找到可运行 teacher_allocation parser 的 Python 环境（缺少 xlrd）")


def main() -> int:
    python_bin = choose_python()
    cmd = [str(python_bin), str(PARSER), *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    raise SystemExit(main())
