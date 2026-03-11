#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5 标准交付回执集成测试（datahub core 版，不含飞书发送）。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = ROOT / "skills" / "teacher-work-datahub" / "scripts" / "delivery" / "build_teacher_semester_timetable.py"
RECEIPT = ROOT / "skills" / "teacher-work-datahub" / "scripts" / "delivery" / "delivery_receipt.py"
PYTHON = Path(sys.executable).resolve()
OUT_DIR = ROOT / "data" / "reports" / "teacher-semester-flow" / "p5-tests"


def run_case(name: str, args: list[str]) -> dict:
    out_base = OUT_DIR / name
    out_base.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(PYTHON), str(BUILD), *args, "--out-base", str(out_base)]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"case {name} failed: rc={proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    result = json.loads(out_base.with_suffix(".json").read_text(encoding="utf-8"))
    receipt_json = subprocess.run(
        [str(PYTHON), str(RECEIPT), "--result-json", str(out_base.with_suffix('.json')), "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    receipt_text = subprocess.run(
        [str(PYTHON), str(RECEIPT), "--result-json", str(out_base.with_suffix('.json')), "--format", "text"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed_receipt = json.loads(receipt_json.stdout)
    assert result["delivery_receipt"] == parsed_receipt, f"case {name}: delivery_receipt mismatch"
    assert result["summary_text"].strip() == receipt_text.stdout.strip(), f"case {name}: summary_text mismatch"
    return result


def assert_common_receipt(case_name: str, result: dict) -> None:
    receipt = result.get("delivery_receipt") or {}
    assert receipt.get("result_status") == "success", f"{case_name}: result_status"
    generation_status = receipt.get("generation_status") or {}
    assert generation_status.get("state") == "success", f"{case_name}: generation_status.state"
    assert generation_status.get("success") is True, f"{case_name}: generation_status.success"
    assert "overall_status" in receipt, f"{case_name}: missing overall_status"
    class_set_check = receipt.get("class_set_check") or {}
    assert "schedule_class_count" in class_set_check, f"{case_name}: missing class_set_check.schedule_class_count"
    assert "allocation_class_count" in class_set_check, f"{case_name}: missing class_set_check.allocation_class_count"
    assert "only_in_schedule" in class_set_check, f"{case_name}: missing class_set_check.only_in_schedule"
    assert "only_in_allocation" in class_set_check, f"{case_name}: missing class_set_check.only_in_allocation"
    assert "diff_summary_path" in receipt, f"{case_name}: missing diff_summary_path"
    outputs = receipt.get("output_file_paths") or {}
    assert outputs.get("image"), f"{case_name}: missing image path"
    assert outputs.get("json"), f"{case_name}: missing json path"
    assert outputs.get("summary"), f"{case_name}: missing summary path"
    source_trace = receipt.get("source_trace") or {}
    assert source_trace.get("kind"), f"{case_name}: missing source kind"
    assert source_trace.get("active_record_id"), f"{case_name}: missing active_record_id"
    assert source_trace.get("source_name"), f"{case_name}: missing source_name"
    send_status = receipt.get("send_status") or {}
    assert "message_id" in send_status, f"{case_name}: missing send_status.message_id"
    assert "method" in send_status, f"{case_name}: missing send_status.method"
    assert "success" in send_status, f"{case_name}: missing send_status.success"
    assert "error_summary" in send_status, f"{case_name}: missing send_status.error_summary"


def main() -> int:
    results = {}

    results["A_core_not_send"] = run_case(
        "case-a-core-not-send",
        [
            "--teacher",
            "吕晓瑞",
        ],
    )
    assert_common_receipt("A_core_not_send", results["A_core_not_send"])
    receipt_a = results["A_core_not_send"]["delivery_receipt"]
    assert receipt_a["overall_status"] == "success", "A: overall_status should be success"
    assert receipt_a["send_status"]["state"] == "not_sent", "A: send state should be not_sent"
    assert receipt_a["send_status"]["success"] is None, "A: send success should be None"
    assert receipt_a["send_status"]["error_summary"] == "未发送", "A: should say 未发送"

    results["B_not_send_tolerance"] = run_case(
        "case-b-not-send-tolerance",
        [
            "--teacher",
            "吕晓",
        ],
    )
    assert_common_receipt("B_not_send_tolerance", results["B_not_send_tolerance"])
    receipt_b = results["B_not_send_tolerance"]["delivery_receipt"]
    assert receipt_b["overall_status"] == "success", "B: overall_status should be success"
    assert receipt_b["send_status"]["state"] == "not_sent", "B: send state should be not_sent"
    assert receipt_b["send_status"]["success"] is None, "B: send success should be None"
    assert receipt_b["teacher_name_tolerance"]["used"] is True, "B: tolerance should be used"
    assert "已按容错名处理" in receipt_b["teacher_name_tolerance"]["note"], "B: tolerance note missing"

    results["C_fallback_with_diff"] = run_case(
        "case-c-fallback-with-diff",
        [
            "--teacher",
            "李亚",
            "--diff-summary-path",
            "data/schedules/catalog/diff-school-schedule-20260306.json",
        ],
    )
    assert_common_receipt("C_fallback_with_diff", results["C_fallback_with_diff"])
    receipt_c = results["C_fallback_with_diff"]["delivery_receipt"]
    assert receipt_c["overall_status"] == "success", "C: overall_status should be success"
    assert receipt_c["send_status"]["state"] == "not_sent", "C: send state should be not_sent"
    assert receipt_c["fallback"]["used"] is True, "C: source fallback should be used"
    assert receipt_c["source_trace"]["kind"] == "school_schedule_no_selfstudy", "C: should trace fallback source"
    assert receipt_c["diff_summary_path"].endswith("data/schedules/catalog/diff-school-schedule-20260306.json"), "C: diff_summary_path should be present"
    assert "版本差异摘要：" in results["C_fallback_with_diff"]["summary_text"], "C: summary should mention diff summary"

    printable = {
        name: {
            "json": result["outputs"]["json"],
            "summary": result["outputs"]["summary"],
            "overall_status": result["delivery_receipt"]["overall_status"],
            "send_state": result["delivery_receipt"]["send_status"]["state"],
            "message_id": result["delivery_receipt"]["send_status"]["message_id"],
            "diff_summary_path": result["delivery_receipt"]["diff_summary_path"],
        }
        for name, result in results.items()
    }
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
