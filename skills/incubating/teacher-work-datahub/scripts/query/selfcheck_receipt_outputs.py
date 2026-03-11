#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = ROOT / "data" / "teacher-work-datahub" / "outputs" / "selfchecks"
CASE_JSON = ROOT / "data" / "reports" / "printables" / "selfcheck-datahub-receipt-case.json"
BUILD = ROOT / "skills" / "teacher-work-datahub" / "scripts" / "delivery" / "build_teacher_semester_timetable.py"
PYTHON = sys.executable


def ensure(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def ensure_case_json() -> Path:
    if CASE_JSON.exists():
        return CASE_JSON
    CASE_JSON.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        PYTHON,
        str(BUILD),
        "--teacher",
        "吕晓瑞",
        "--schedule-type",
        "semester",
        "--output-format",
        "image",
        "--out-base",
        str(CASE_JSON.with_suffix("")),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
    stdout = proc.stdout.strip()
    if stdout:
        lines = [line for line in stdout.splitlines() if line.strip()]
        payload = json.loads("\n".join(lines[1:]) if lines and lines[0].endswith('.jpg') else stdout)
        CASE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ensure(CASE_JSON.exists(), f"未生成 CASE_JSON: {CASE_JSON}")
    return CASE_JSON


def main() -> int:
    case_json = ensure_case_json()
    obj = json.loads(case_json.read_text(encoding="utf-8"))
    outputs = obj.get("outputs") or {}
    receipt = obj.get("delivery_receipt") or {}
    output_paths = receipt.get("output_file_paths") or {}
    source_trace = receipt.get("source_trace") or {}

    cases = []

    ensure(outputs.get("image") == output_paths.get("image"), "receipt image path should match outputs.image")
    ensure(outputs.get("json") == output_paths.get("json"), "receipt json path should match outputs.json")
    ensure(outputs.get("summary") == output_paths.get("summary"), "receipt summary path should match outputs.summary")
    cases.append({"case": "receipt_output_paths_match", "status": "passed"})

    ensure(receipt.get("overall_status") == obj.get("status"), "receipt overall_status should match result status")
    ensure(
        source_trace.get("active_record_id") == (((obj.get("selected_source") or {}).get("selected_trace") or {}).get("record_id")),
        "receipt source_trace active_record_id should match selected_source trace",
    )
    cases.append({"case": "receipt_status_and_trace_match", "status": "passed", "active_record_id": source_trace.get("active_record_id", "")})

    report = {
        "report": "receipt-outputs-selfcheck",
        "counts": {"total": len(cases), "passed": len(cases), "failed": 0},
        "cases": cases,
        "fixture": str(case_json),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "receipt-outputs-selfcheck.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
