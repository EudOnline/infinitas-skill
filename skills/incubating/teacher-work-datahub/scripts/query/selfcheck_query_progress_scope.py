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
    query = root / "skills" / "teacher-work-datahub" / "scripts" / "query" / "query_progress_scope_datahub.py"
    fixture_mode = os.getenv("TEACHER_WORK_DATAHUB_FIXTURE", "").strip() == "minimal-datahub"
    cases = []

    if fixture_mode:
        mid = run_json([PYTHON, str(query), "--grade", "测试高一", "--subject", "物理", "--exam", "midterm"], cwd=root)
        ensure(mid.get("success") is True, "fixture midterm scope should succeed")
        ensure(mid.get("count") == 1, "fixture midterm should return one row")
        ensure("测试范围" in (((mid.get("rows") or [{}])[0].get("midterm") or {}).get("text") or ""), "fixture midterm scope text should mention 测试范围")
        cases.append({"case": "fixture_midterm_scope", "status": "passed"})

        final = run_json([PYTHON, str(query), "--grade", "测试高一", "--subject", "物理", "--exam", "final"], cwd=root)
        ensure(final.get("success") is True, "fixture final scope should succeed")
        ensure(final.get("count") == 1, "fixture final should return one row")
        ensure(bool(((final.get("rows") or [{}])[0].get("final") or {}).get("text")), "fixture final scope text should be non-empty")
        cases.append({"case": "fixture_final_scope", "status": "passed"})
    else:
        mid = run_json([PYTHON, str(query), "--grade", "高二", "--subject", "物理", "--exam", "midterm"], cwd=root)
        ensure(mid.get("success") is True, "midterm scope should succeed")
        ensure(mid.get("count") == 1, "midterm should return one row")
        ensure("选必" in (((mid.get("rows") or [{}])[0].get("midterm") or {}).get("text") or ""), "midterm scope text should mention 选必")
        cases.append({"case": "midterm_scope", "status": "passed"})

        final = run_json([PYTHON, str(query), "--grade", "高二", "--subject", "物理", "--exam", "final"], cwd=root)
        ensure(final.get("success") is True, "final scope should succeed")
        ensure(final.get("count") == 1, "final should return one row")
        ensure(bool(((final.get("rows") or [{}])[0].get("final") or {}).get("text")), "final scope text should be non-empty")
        cases.append({"case": "final_scope", "status": "passed"})

    report = {
        "report": "query-progress-scope-selfcheck",
        "counts": {"total": len(cases), "passed": len(cases), "failed": 0},
        "cases": cases,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "query-progress-scope-selfcheck.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
