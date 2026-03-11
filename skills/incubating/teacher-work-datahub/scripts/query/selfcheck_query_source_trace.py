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
    trace = root / "skills" / "teacher-work-datahub" / "scripts" / "query" / "query_source_trace.py"
    cases = []

    fixture_mode = os.getenv("TEACHER_WORK_DATAHUB_FIXTURE", "").strip() == "minimal-datahub"

    if fixture_mode:
        by_record = run_json([PYTHON, str(trace), "--workspace-root", str(root), "--record-id", "fixture-src-grade-schedule-001"], cwd=root)
        ensure(by_record.get("count") == 1, "fixture trace by record id should return exactly one record")
        rec = (by_record.get("records") or [{}])[0]
        ensure(rec.get("kind") == "grade_schedule_with_selfstudy", "fixture record kind should match")
        cases.append({"case": "fixture_trace_by_record_id", "status": "passed", "record_id": rec.get("record_id", "")})
    else:
        by_record = run_json([PYTHON, str(trace), "--workspace-root", str(root), "--record-id", "src-345c54a3a876"], cwd=root)
        ensure(by_record.get("count") == 1, "trace by record id should return exactly one record")
        rec = (by_record.get("records") or [{}])[0]
        ensure(rec.get("kind") == "grade_schedule_with_selfstudy", "record kind should match")
        cases.append({"case": "trace_by_record_id", "status": "passed", "record_id": rec.get("record_id", "")})

        by_kind = run_json([PYTHON, str(trace), "--workspace-root", str(root), "--kind", "school_schedule_no_selfstudy", "--semester", "S2", "--status", "active"], cwd=root)
        ensure(by_kind.get("count") == 1, "active school_schedule_no_selfstudy S2 should be unique")
        cases.append({"case": "trace_by_kind_semester_status", "status": "passed", "count": by_kind.get("count")})

    report = {
        "report": "query-source-trace-selfcheck",
        "counts": {"total": len(cases), "passed": len(cases), "failed": 0},
        "cases": cases,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "query-source-trace-selfcheck.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
