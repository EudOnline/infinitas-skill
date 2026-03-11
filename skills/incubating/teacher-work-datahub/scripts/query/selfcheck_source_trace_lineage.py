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
    lineage_path = root / "data" / "teacher-work-datahub" / "curated" / "lineage" / "source_lineage.json"
    fixture_mode = os.getenv("TEACHER_WORK_DATAHUB_FIXTURE", "").strip() == "minimal-datahub"

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    records = lineage.get("records") or []
    if fixture_mode:
        ensure(len(records) >= 2, "fixture lineage records should be >= 2")
    else:
        ensure(len(records) >= 20, "lineage records should be >= 20")

    cases = []
    if fixture_mode:
        active_sched = run_json([PYTHON, str(trace), "--workspace-root", str(root), "--kind", "grade_schedule_with_selfstudy", "--semester", "S1", "--status", "active"], cwd=root)
        ensure(active_sched.get("count") == 1, "fixture active S1 grade schedule trace should return one record")
        rid = (active_sched.get("records") or [{}])[0].get("record_id", "")
        ensure(rid == "fixture-src-grade-schedule-001", "fixture active grade schedule record_id should match expected")
        cases.append({"case": "fixture_trace_grade_schedule_s1_active", "status": "passed", "record_id": rid})

        lineage_active = [r for r in records if r.get("record_id") == "fixture-src-grade-schedule-001"]
        ensure(len(lineage_active) == 1, "fixture lineage should contain active grade schedule record")
        ensure(lineage_active[0].get("status") == "active", "fixture lineage grade schedule status should be active")
        cases.append({"case": "fixture_lineage_contains_active_grade_schedule", "status": "passed", "record_id": "fixture-src-grade-schedule-001"})
    else:
        active_sched = run_json([PYTHON, str(trace), "--workspace-root", str(root), "--kind", "grade_schedule_with_selfstudy", "--semester", "S2", "--status", "active"], cwd=root)
        ensure(active_sched.get("count") == 1, "active S2 grade schedule trace should return one record")
        rid = (active_sched.get("records") or [{}])[0].get("record_id", "")
        ensure(rid == "src-345c54a3a876", "active S2 grade schedule record_id should match expected")
        cases.append({"case": "trace_grade_schedule_s2_active", "status": "passed", "record_id": rid})

        active_alloc = run_json([PYTHON, str(trace), "--workspace-root", str(root), "--domain", "teacher_allocation", "--semester", "S2", "--status", "active"], cwd=root)
        ensure(active_alloc.get("count") >= 1, "active S2 teacher_allocation trace should exist")
        cases.append({"case": "trace_teacher_allocation_s2_active", "status": "passed", "count": active_alloc.get("count")})

        lineage_active = [r for r in records if r.get("record_id") == "src-345c54a3a876"]
        ensure(len(lineage_active) == 1, "lineage should contain active grade schedule record")
        ensure(lineage_active[0].get("status") == "active", "lineage active grade schedule status should be active")
        cases.append({"case": "lineage_contains_active_grade_schedule", "status": "passed", "record_id": "src-345c54a3a876"})

    report = {
        "report": "source-trace-lineage-selfcheck",
        "counts": {"total": len(cases), "passed": len(cases), "failed": 0},
        "cases": cases,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "source-trace-lineage-selfcheck.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
