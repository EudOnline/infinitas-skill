#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[4]
PYTHON = sys.executable


def ensure(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def run_json(cmd: list[str], *, cwd: Path) -> dict:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default="", help="工作区根目录；默认当前教师工作区")
    args = parser.parse_args()

    root = Path(args.workspace_root).expanduser().resolve() if args.workspace_root else DEFAULT_ROOT
    os.environ["TEACHER_WORK_DATAHUB_ROOT"] = str(root)
    out_dir = root / "data" / "teacher-work-datahub" / "outputs" / "selfchecks"
    query_scope = root / "skills" / "teacher-work-datahub" / "scripts" / "query" / "query_progress_scope_datahub.py"
    fixture_mode = os.getenv("TEACHER_WORK_DATAHUB_FIXTURE", "").strip() == "minimal-datahub"
    cases = []

    if fixture_mode:
        scope = run_json([PYTHON, str(query_scope), "--grade", "测试高一", "--subject", "物理", "--exam", "midterm"], cwd=root)
        ensure(scope.get("success") is True, "fixture progress scope should succeed")
        ensure(scope.get("count") == 1, "fixture progress scope should return one row")
        rows = scope.get("rows") or []
        text = ((rows[0].get("midterm") or {}).get("text") if rows else "") or ""
        ensure("测试范围" in text, "fixture progress scope text should mention 测试范围")
        cases.append({"case": "fixture_progress_scope", "status": "passed", "record_id": (scope.get("source") or {}).get("record_id", ""), "text": text})
    else:
        scope = run_json([PYTHON, str(query_scope), "--grade", "高二", "--subject", "物理", "--exam", "midterm"], cwd=root)
        ensure(scope.get("success") is True, "progress scope should succeed")
        ensure((scope.get("source") or {}).get("record_id"), "progress scope should return active source record_id")
        ensure(scope.get("count") == 1, "progress scope should return one row for 高二物理期中")
        rows = scope.get("rows") or []
        text = ((rows[0].get("midterm") or {}).get("text") if rows else "") or ""
        ensure("选必" in text, "progress scope text should mention 选必")
        cases.append({"case": "progress_scope", "status": "passed", "record_id": (scope.get("source") or {}).get("record_id", ""), "text": text})

    report = {
        "report": "teaching-progress-selfcheck",
        "counts": {"total": len(cases), "passed": len(cases), "failed": 0},
        "cases": cases,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "teaching-progress-selfcheck.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
