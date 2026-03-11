#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
TARGET = WORKSPACE_ROOT / "skills" / "teacher-work-datahub" / "scripts" / "query" / "query_progress_nl_datahub.py"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python3 answer_progress_query_datahub.py \"查询文本\"")
        return 1
    query_text = sys.argv[1].strip()
    if not query_text:
        print("查询文本不能为空")
        return 1
    cmd = [sys.executable, str(TARGET), "--text", query_text, "--format", "text"]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    raise SystemExit(main())
