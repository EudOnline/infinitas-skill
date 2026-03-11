#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

DEFAULT_ROOT = Path(__file__).resolve().parents[4]


def ensure(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default="", help="工作区根目录；默认当前教师工作区")
    args = parser.parse_args()

    root = Path(args.workspace_root).expanduser().resolve() if args.workspace_root else DEFAULT_ROOT
    os.environ["TEACHER_WORK_DATAHUB_ROOT"] = str(root)
    out_dir = root / "data" / "teacher-work-datahub" / "outputs" / "selfchecks"
    active_sources = root / "data" / "teacher-work-datahub" / "curated" / "indexes" / "active_sources.json"

    data = json.loads(active_sources.read_text(encoding="utf-8"))
    bucket = data.get("by_semester") or data.get("semesters") or {}
    fixture_mode = os.getenv("TEACHER_WORK_DATAHUB_FIXTURE", "").strip() == "minimal-datahub"
    semester_key = "2099-2100:S1" if fixture_mode else "S2"
    bucket_item = bucket.get(semester_key) or bucket.get("S2") or {}

    cases = []
    expected_kinds = ["teacher_allocation", "grade_schedule_with_selfstudy"]
    if fixture_mode:
        expected_kinds.append("teaching_progress_total_table")
    else:
        expected_kinds.append("school_schedule_no_selfstudy")
    for kind in expected_kinds:
        item = bucket_item.get(kind) or {}
        ensure(item, f"{semester_key} missing active source for {kind}")
        ensure(item.get("record_id"), f"{kind} should have record_id")
        cases.append({"case": kind, "status": "passed", "record_id": item.get("record_id"), "source_name": item.get("source_name", "")})

    report = {
        "report": "active-sources-selfcheck",
        "counts": {"total": len(cases), "passed": len(cases), "failed": 0},
        "cases": cases,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "active-sources-selfcheck.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
