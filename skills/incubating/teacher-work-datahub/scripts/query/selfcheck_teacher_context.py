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

from resolve_teacher_context import resolve_teacher_context  # noqa: E402


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
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = []

    fixture_mode = os.getenv("TEACHER_WORK_DATAHUB_FIXTURE", "").strip() == "minimal-datahub"

    if fixture_mode:
        teacher = resolve_teacher_context(teacher="测试教师A")
        ensure(teacher is not None, "fixture teacher should resolve")
        ensure(teacher.get("teacher") == "测试教师A", "fixture teacher should match")
        ensure(teacher.get("classes") == ["9901班", "9902班"], "fixture classes should match")
        cases.append({"case": "fixture_teacher_context", "status": "passed", "teacher": teacher.get("teacher"), "classes": teacher.get("classes")})
    else:
        fan = resolve_teacher_context(teacher="樊丰丽")
        ensure(fan is not None, "樊丰丽 context should resolve")
        ensure(fan.get("classes") == ["2505班", "2506班"], "樊丰丽 should shrink to current sheet classes")
        ensure(fan.get("sheet_scope") == "2026.3", "樊丰丽 sheet_scope should be 2026.3")
        cases.append({"case": "current_sheet_shrink", "status": "passed", "classes": fan.get("classes"), "sheet_scope": fan.get("sheet_scope")})

        lv = resolve_teacher_context(teacher="吕晓")
        ensure(lv is not None, "吕晓 tolerance should resolve")
        ensure(lv.get("teacher") == "吕晓瑞", "吕晓 should resolve to 吕晓瑞")
        ensure(lv.get("disambiguation_note") == "已按容错名处理：吕晓 -> 吕晓瑞", "吕晓 note should match")
        cases.append({"case": "name_tolerance", "status": "passed", "teacher": lv.get("teacher"), "note": lv.get("disambiguation_note")})

    report = {
        "report": "teacher-context-selfcheck",
        "counts": {"total": len(cases), "passed": len(cases), "failed": 0},
        "cases": cases,
    }
    out = out_dir / "teacher-context-selfcheck.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
