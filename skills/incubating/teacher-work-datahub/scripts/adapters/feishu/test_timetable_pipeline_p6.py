#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Feishu adapter 集成回归测试（兼容旧名 P6）。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[5]
BUILD = ROOT / "skills" / "teacher-work-datahub" / "scripts" / "adapters" / "feishu" / "build_teacher_semester_timetable.py"
RECEIPT = ROOT / "skills" / "teacher-work-datahub" / "scripts" / "adapters" / "feishu" / "delivery_receipt.py"
def choose_python() -> Path:
    candidates = [
        ROOT / ".venv-schedule" / "bin" / "python",
        ROOT / ".venv" / "bin" / "python",
        Path("/usr/bin/python3"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise SystemExit("未找到可运行 Feishu adapter 集成回归的 Python 环境")


PYTHON = choose_python()
OUT_DIR = ROOT / "data" / "reports" / "teacher-semester-flow" / "p6"
REPORT_JSON = OUT_DIR / "p6-report.json"
REPORT_TXT = OUT_DIR / "p6-report.txt"
ORIGINAL_TEACHER_ALLOCATION_CANDIDATES = [
    ROOT / "data" / "teacher-work-datahub" / "curated" / "teacher-allocation" / "teacher_allocation_latest_allgrades.json",
    ROOT / "data" / "schedules" / "teacher_allocation_202603_parsed_allgrades.json",
]
ORIGINAL_TEACHER_ALLOCATION = next((p for p in ORIGINAL_TEACHER_ALLOCATION_CANDIDATES if p.exists()), ORIGINAL_TEACHER_ALLOCATION_CANDIDATES[0])
SUCCESS_OPEN_ID = "ou_e9fde4fe5ab9d9de2349699d529de8a3"
INVALID_OPEN_ID = "ou_invalid_not_exist"


class CaseFailure(AssertionError):
    pass


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise CaseFailure(message)


def create_zero_hit_teacher_index_override() -> Path:
    data = {
        "schema_version": "teacher-work-datahub.teacher-index.v1",
        "teachers": {
            "霍卫红": {
                "academic_year": "2025-2026",
                "semester": "S2",
                "subjects": ["历史", "班主任"],
                "classes": ["2401班", "2402班"],
                "grades": ["高二"],
                "active_source": {
                    "record_id": "test-zero-hit",
                    "kind": "teacher_allocation"
                },
                "evidence": [
                    {"teacher_raw": "霍卫红", "sheet": "2026.3", "subject": "班主任", "class": "2401"},
                    {"teacher_raw": "霍卫红", "sheet": "2025.9", "subject": "历史", "class": "2401"},
                    {"teacher_raw": "霍卫红", "sheet": "2025.9", "subject": "历史", "class": "2402"}
                ]
            }
        }
    }
    patched = OUT_DIR / "fixtures" / "teacher-index-zero-hit-hwh-history.json"
    patched.parent.mkdir(parents=True, exist_ok=True)
    patched.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return patched


def create_ambiguity_teacher_allocation() -> Path:
    data = json.loads(ORIGINAL_TEACHER_ALLOCATION.read_text(encoding="utf-8"))
    index = data.get("focus_grade_teacher_index") or {}
    index["李亚琼"] = [
        {
            "teacher_raw": "李亚琼",
            "class": "2504",
            "subject": "物理",
            "sheet": "2026.3",
        }
    ]
    index["李亚倩"] = [
        {
            "teacher_raw": "李亚倩",
            "class": "2403",
            "subject": "生物",
            "sheet": "2026.3",
        }
    ]
    patched = OUT_DIR / "fixtures" / "teacher-allocation-ambiguity-liya.json"
    patched.parent.mkdir(parents=True, exist_ok=True)
    patched.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return patched


def create_ambiguity_teacher_index_override() -> Path:
    data = {
        "schema_version": "teacher-work-datahub.teacher-index.v1",
        "teachers": {
            "李亚琼": {
                "academic_year": "2025-2026",
                "semester": "S2",
                "subjects": ["物理"],
                "classes": ["2504班"],
                "grades": ["高三"],
                "active_source": {"record_id": "test-ambiguity", "kind": "teacher_allocation"},
                "evidence": [
                    {"teacher_raw": "李亚琼", "sheet": "2026.3", "subject": "物理", "class": "2504"}
                ],
            },
            "李亚倩": {
                "academic_year": "2025-2026",
                "semester": "S2",
                "subjects": ["生物"],
                "classes": ["2403班"],
                "grades": ["高二"],
                "active_source": {"record_id": "test-ambiguity", "kind": "teacher_allocation"},
                "evidence": [
                    {"teacher_raw": "李亚倩", "sheet": "2026.3", "subject": "生物", "class": "2403"}
                ],
            },
        },
    }
    patched = OUT_DIR / "fixtures" / "teacher-index-ambiguity-liya.json"
    patched.parent.mkdir(parents=True, exist_ok=True)
    patched.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return patched


def run_case(name: str, args: List[str], expect_rc: int = 0) -> Dict[str, Any]:
    out_base = OUT_DIR / name
    out_base.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".jpg", ".json", ".txt"):
        p = out_base.with_suffix(suffix)
        if p.exists():
            p.unlink()

    cmd = [str(PYTHON), str(BUILD), *args, "--python-bin", str(PYTHON), "--out-base", str(out_base)]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    ensure(proc.returncode == expect_rc, f"{name}: rc={proc.returncode}, expect={expect_rc}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    result_json = out_base.with_suffix(".json")
    result_txt = out_base.with_suffix(".txt")
    ensure(result_json.exists(), f"{name}: missing result json {result_json}")
    ensure(result_txt.exists(), f"{name}: missing result txt {result_txt}")

    result = json.loads(result_json.read_text(encoding="utf-8"))

    receipt_json = subprocess.run(
        [str(PYTHON), str(RECEIPT), "--result-json", str(result_json), "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    receipt_text = subprocess.run(
        [str(PYTHON), str(RECEIPT), "--result-json", str(result_json), "--format", "text"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed_receipt = json.loads(receipt_json.stdout)
    ensure(result.get("delivery_receipt") == parsed_receipt, f"{name}: delivery_receipt mismatch")
    ensure(result.get("summary_text", "").strip() == receipt_text.stdout.strip(), f"{name}: summary_text mismatch")

    return {
        "name": name,
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "result": result,
        "out_base": str(out_base),
    }


def assert_common_success(case: Dict[str, Any]) -> None:
    name = case["name"]
    result = case["result"]
    receipt = result.get("delivery_receipt") or {}

    ensure(result.get("status") == "success", f"{name}: result.status should be success")
    ensure(receipt.get("result_status") == "success", f"{name}: receipt.result_status should be success")
    generation_status = receipt.get("generation_status") or {}
    ensure(generation_status.get("state") == "success", f"{name}: generation_status.state should be success")
    ensure(generation_status.get("success") is True, f"{name}: generation_status.success should be true")
    ensure("overall_status" in receipt, f"{name}: missing overall_status")

    teacher_inference = result.get("teacher_inference") or {}
    ensure("requested_teacher" in teacher_inference, f"{name}: missing teacher_inference.requested_teacher")
    ensure("matched_teacher" in teacher_inference, f"{name}: missing teacher_inference.matched_teacher")
    ensure("teacher_fallback_used" in teacher_inference, f"{name}: missing teacher_inference.teacher_fallback_used")
    ensure("teacher_fallback_note" in teacher_inference, f"{name}: missing teacher_inference.teacher_fallback_note")
    ensure("sheet_scope" in teacher_inference, f"{name}: missing teacher_inference.sheet_scope")
    ensure("sheet_scope_note" in teacher_inference, f"{name}: missing teacher_inference.sheet_scope_note")
    ensure("ambiguity_detected" in teacher_inference, f"{name}: missing teacher_inference.ambiguity_detected")
    ensure("ambiguity_note" in teacher_inference, f"{name}: missing teacher_inference.ambiguity_note")
    ensure("ambiguity_options" in teacher_inference, f"{name}: missing teacher_inference.ambiguity_options")
    ensure("disambiguation_used" in teacher_inference, f"{name}: missing teacher_inference.disambiguation_used")
    ensure("disambiguation_note" in teacher_inference, f"{name}: missing teacher_inference.disambiguation_note")

    request_parse = result.get("request_parse") or {}
    ensure("request_text" in request_parse, f"{name}: missing request_parse.request_text")
    ensure("teacher" in request_parse, f"{name}: missing request_parse.teacher")
    ensure("class_hints" in request_parse, f"{name}: missing request_parse.class_hints")
    ensure("subject_hints" in request_parse, f"{name}: missing request_parse.subject_hints")
    ensure("schedule_type" in request_parse, f"{name}: missing request_parse.schedule_type")
    ensure("week_parity" in request_parse, f"{name}: missing request_parse.week_parity")
    ensure("output_format" in request_parse, f"{name}: missing request_parse.output_format")
    ensure("send_requested" in request_parse, f"{name}: missing request_parse.send_requested")
    ensure("auto_parse_used" in request_parse, f"{name}: missing request_parse.auto_parse_used")

    selected_source = result.get("selected_source") or {}
    ensure("selected_kind" in selected_source, f"{name}: missing selected_source.selected_kind")
    ensure("source_has_evening_slots" in selected_source, f"{name}: missing selected_source.source_has_evening_slots")
    ensure("fallback_used" in selected_source, f"{name}: missing selected_source.fallback_used")
    ensure("fallback_reason" in selected_source, f"{name}: missing selected_source.fallback_reason")

    class_set_check = result.get("class_set_check") or {}
    ensure("schedule_class_count" in class_set_check, f"{name}: missing result.class_set_check.schedule_class_count")
    ensure("allocation_class_count" in class_set_check, f"{name}: missing result.class_set_check.allocation_class_count")
    ensure("only_in_schedule" in class_set_check, f"{name}: missing result.class_set_check.only_in_schedule")
    ensure("only_in_allocation" in class_set_check, f"{name}: missing result.class_set_check.only_in_allocation")
    receipt_class_set_check = receipt.get("class_set_check") or {}
    ensure("schedule_class_count" in receipt_class_set_check, f"{name}: missing receipt.class_set_check.schedule_class_count")
    ensure("allocation_class_count" in receipt_class_set_check, f"{name}: missing receipt.class_set_check.allocation_class_count")
    ensure("only_in_schedule" in receipt_class_set_check, f"{name}: missing receipt.class_set_check.only_in_schedule")
    ensure("only_in_allocation" in receipt_class_set_check, f"{name}: missing receipt.class_set_check.only_in_allocation")
    ensure("diff_summary_path" in receipt, f"{name}: missing receipt.diff_summary_path")

    receipt_selected = receipt.get("selected_source") or {}
    ensure("kind" in receipt_selected, f"{name}: missing receipt.selected_source.kind")
    ensure("has_evening_slots" in receipt_selected, f"{name}: missing receipt.selected_source.has_evening_slots")

    send_status = receipt.get("send_status") or {}
    ensure("state" in send_status, f"{name}: missing send_status.state")
    ensure("success" in send_status, f"{name}: missing send_status.success")
    ensure("method" in send_status, f"{name}: missing send_status.method")
    ensure("message_id" in send_status, f"{name}: missing send_status.message_id")
    ensure("error_summary" in send_status, f"{name}: missing send_status.error_summary")

    tolerance = receipt.get("teacher_name_tolerance") or {}
    ensure("used" in tolerance, f"{name}: missing teacher_name_tolerance.used")
    ensure("note" in tolerance, f"{name}: missing teacher_name_tolerance.note")
    ensure("requested_name" in tolerance, f"{name}: missing teacher_name_tolerance.requested_name")
    ensure("matched_name" in tolerance, f"{name}: missing teacher_name_tolerance.matched_name")

    fallback = receipt.get("fallback") or {}
    ensure("used" in fallback, f"{name}: missing fallback.used")
    ensure("note" in fallback, f"{name}: missing fallback.note")

    outputs = result.get("outputs") or {}
    for key in ("json", "summary"):
        ensure(outputs.get(key), f"{name}: outputs.{key} missing")
        ensure(Path(outputs[key]).exists(), f"{name}: outputs.{key} file missing")
    image_path = outputs.get("image")
    ensure(image_path, f"{name}: outputs.image missing")
    ensure(Path(image_path).exists(), f"{name}: outputs.image file missing")
    ensure("final" in outputs, f"{name}: outputs.final missing")
    final_path = outputs.get("final")
    ensure(final_path, f"{name}: outputs.final empty")
    ensure(Path(final_path).exists(), f"{name}: outputs.final file missing")
    if outputs.get("pdf"):
        ensure(Path(outputs.get("pdf")).exists(), f"{name}: outputs.pdf file missing")

    ensure(result.get("delivery_receipt"), f"{name}: missing delivery_receipt")
    ensure(result.get("send_result", None) is None or isinstance(result.get("send_result"), dict), f"{name}: send_result invalid")


def assert_failed_case(case: Dict[str, Any], expected_error_keyword: str = "命中数为0") -> None:
    name = case["name"]
    result = case["result"]
    receipt = result.get("delivery_receipt") or {}
    error = result.get("error") or {}

    ensure(result.get("status") == "failed", f"{name}: result.status should be failed")
    ensure(receipt.get("result_status") == "failed", f"{name}: receipt.result_status should be failed")
    generation_status = receipt.get("generation_status") or {}
    ensure(generation_status.get("state") == "failed", f"{name}: generation_status.state should be failed")
    ensure(generation_status.get("success") is False, f"{name}: generation_status.success should be false")
    ensure(receipt.get("overall_status") == "failed", f"{name}: overall_status should be failed")
    ensure(error.get("message"), f"{name}: error.message should not be empty")
    if expected_error_keyword:
        ensure(expected_error_keyword in error.get("message", ""), f"{name}: should mention {expected_error_keyword}")
    ensure((receipt.get("send_status") or {}).get("state") == "not_sent", f"{name}: failed case send_status.state should be not_sent")
    ensure((receipt.get("error") or {}).get("message") == error.get("message"), f"{name}: receipt.error.message mismatch")
    image_path = (result.get("outputs") or {}).get("image", "")
    ensure(image_path, f"{name}: outputs.image missing")
    ensure(not Path(image_path).exists(), f"{name}: failed case should not create image")


def check_case_a(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    receipt = result["delivery_receipt"]
    ensure(result["teacher_inference"]["matched_teacher"] == "吕晓瑞", "A: teacher match")
    ensure(result["selected_source"]["selected_kind"] == "grade_schedule_with_selfstudy", "A: selected source")
    ensure(result["selected_source"]["source_has_evening_slots"] is True, "A: evening slots")
    ensure(receipt["fallback"]["used"] is False, "A: fallback should be false")
    ensure(receipt["overall_status"] == "success", "A: overall_status should be success")
    ensure(receipt["send_status"]["state"] == "not_sent", "A: send should be not_sent")
    ensure(receipt["teacher_name_tolerance"]["used"] is False, "A: tolerance should be false")
    ensure(receipt["diff_summary_path"].endswith("data/schedules/catalog/diff-high2-vs-semantic.json"), "A: diff_summary_path")
    return {
        "scenario": "A 吕晓瑞优先源成功",
        "status": "passed",
        "selected_source": result["selected_source"]["selected_kind"],
        "source_has_evening_slots": result["selected_source"]["source_has_evening_slots"],
        "send_state": receipt["send_status"]["state"],
    }


def check_case_b(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    receipt = result["delivery_receipt"]
    ensure(result["teacher_inference"]["matched_teacher"] == "李亚琼", "B: teacher match")
    ensure(result["selected_source"]["selected_kind"] == "school_schedule_no_selfstudy", "B: selected source")
    ensure(result["selected_source"]["source_has_evening_slots"] is False, "B: evening slots")
    ensure(receipt["fallback"]["used"] is True, "B: fallback should be true")
    ensure("全校无自习课表" in receipt["fallback"]["note"], "B: fallback note")
    ensure(receipt["overall_status"] == "success", "B: overall_status should be success")
    ensure(receipt["send_status"]["state"] == "not_sent", "B: send should be not_sent")
    ensure(receipt["teacher_name_tolerance"]["used"] is False, "B: tolerance should be false")
    return {
        "scenario": "B 李亚琼 fallback no_selfstudy",
        "status": "passed",
        "selected_source": result["selected_source"]["selected_kind"],
        "source_has_evening_slots": result["selected_source"]["source_has_evening_slots"],
        "fallback": receipt["fallback"],
    }


def check_case_c(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    receipt = result["delivery_receipt"]
    ensure(result["teacher_inference"]["requested_teacher"] == "吕晓", "C: requested teacher")
    ensure(result["teacher_inference"]["matched_teacher"] == "吕晓瑞", "C: matched teacher")
    ensure(result["teacher_inference"]["teacher_fallback_used"] is True, "C: teacher fallback used")
    ensure(receipt["teacher_name_tolerance"]["used"] is True, "C: tolerance used")
    ensure("已按容错名处理" in receipt["teacher_name_tolerance"]["note"], "C: tolerance note")
    ensure(receipt["overall_status"] == "success", "C: overall_status should be success")
    ensure(result["selected_source"]["selected_kind"] == "grade_schedule_with_selfstudy", "C: selected source")
    return {
        "scenario": "C 姓名容错",
        "status": "passed",
        "teacher_name_tolerance": receipt["teacher_name_tolerance"],
        "selected_source": result["selected_source"]["selected_kind"],
    }


def check_case_d(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_failed_case(case)
    result = case["result"]
    receipt = result["delivery_receipt"]
    ensure(result["teacher_inference"]["matched_teacher"] == "霍卫红", "D: matched teacher")
    ensure(result["subject"] in {"历史", "班主任"}, "D: subject should follow zero-hit fixture context")
    ensure(result["selected_source"]["selected_kind"] == "grade_schedule_with_selfstudy", "D: selected source")
    ensure(result["selected_source"]["source_has_evening_slots"] is True, "D: evening slots")
    ensure(receipt["fallback"]["used"] is False, "D: fallback should be false")
    return {
        "scenario": "D 命中数为0失败",
        "status": "passed",
        "error": result["error"],
        "selected_source": result["selected_source"]["selected_kind"],
    }


def check_case_e(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    receipt = result["delivery_receipt"]
    ensure(receipt["overall_status"] == "success", "E: overall_status")
    ensure(receipt["send_status"]["state"] == "success", "E: send state")
    ensure(receipt["send_status"]["success"] is True, "E: send success")
    ensure(receipt["send_status"]["message_id"], "E: message id required")
    ensure(result.get("send_result", {}).get("success") is True, "E: send_result.success")
    return {
        "scenario": "E 发送成功",
        "status": "passed",
        "send_result": result["send_result"],
        "delivery_receipt": receipt["send_status"],
    }


def check_case_f(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    receipt = result["delivery_receipt"]
    ensure(result.get("send_result") is None, "F: send_result should be None")
    ensure(receipt["overall_status"] == "success", "F: overall_status")
    ensure(receipt["send_status"]["state"] == "not_sent", "F: send state")
    ensure(receipt["send_status"]["success"] is None, "F: send success should be None")
    ensure(receipt["send_status"]["error_summary"] == "未发送", "F: error summary")
    return {
        "scenario": "F 不发送",
        "status": "passed",
        "send_status": receipt["send_status"],
    }


def check_case_g(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    receipt = result["delivery_receipt"]
    ensure(receipt["overall_status"] == "partial_success", "G: overall_status should be partial_success")
    ensure(receipt["send_status"]["state"] == "failed", "G: send state")
    ensure(receipt["send_status"]["success"] is False, "G: send success")
    ensure(result.get("send_result", {}).get("success") is False, "G: send_result.success")
    ensure(receipt["send_status"]["error_summary"], "G: error summary")
    ensure(result["selected_source"]["selected_kind"] == "school_schedule_no_selfstudy", "G: selected source")
    ensure(receipt["fallback"]["used"] is True, "G: fallback should be true")
    return {
        "scenario": "G 发送失败",
        "status": "passed",
        "send_result": result["send_result"],
        "delivery_receipt": receipt["send_status"],
    }


def check_case_h_current_sheet_scope(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    receipt = result["delivery_receipt"]
    ti = result["teacher_inference"]

    ensure(ti["matched_teacher"] == "樊丰丽", "H: matched teacher")
    ensure(ti["sheet_scope"] == "2026.3", "H: sheet_scope should be 2026.3")
    ensure("收敛" in ti.get("sheet_scope_note", ""), "H: sheet_scope_note should mention 收敛")
    ensure(result["classes"] == ["2505班", "2506班"], "H: classes should be narrowed to current sheet")
    ensure(result["selected_source"]["selected_kind"] == "school_schedule_no_selfstudy", "H: should fallback to school schedule")
    ensure(result["selected_source"]["source_has_evening_slots"] is False, "H: no evening slots")
    ensure(receipt["fallback"]["used"] is True, "H: fallback should be true")
    ensure(receipt["overall_status"] == "success", "H: overall_status should be success")
    ensure(receipt["send_status"]["state"] == "not_sent", "H: send should be not_sent")

    return {
        "scenario": "H 樊丰丽当前sheet收敛",
        "status": "passed",
        "sheet_scope": ti["sheet_scope"],
        "classes": result["classes"],
        "selected_source": result["selected_source"]["selected_kind"],
    }


def check_case_i_name_ambiguity(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_failed_case(case, expected_error_keyword="教师名存在歧义")
    result = case["result"]
    ti = result.get("teacher_inference") or {}

    ensure(ti.get("ambiguity_detected") is True, "I: ambiguity_detected should be true")
    options = ti.get("ambiguity_options") or []
    ensure(len(options) >= 2, "I: ambiguity_options should contain >=2 candidates")
    names = [x.get("matched_teacher") for x in options]
    ensure("李亚琼" in names and "李亚倩" in names, "I: ambiguity options should include 李亚琼/李亚倩")

    return {
        "scenario": "I 同名歧义拦截",
        "status": "passed",
        "ambiguity_note": ti.get("ambiguity_note", ""),
        "options": options,
    }


def check_case_j_hint_disambiguation(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    ti = result.get("teacher_inference") or {}

    ensure(ti.get("matched_teacher") == "李亚琼", "J: should disambiguate to 李亚琼")
    ensure(ti.get("disambiguation_used") is True, "J: disambiguation_used should be true")
    ensure("2504班" in ti.get("disambiguation_note", ""), "J: note should mention 2504班")
    ensure(result.get("classes") == ["2504班"], "J: classes should be 李亚琼的班级")
    ensure(result.get("subject") == "物理", "J: subject should be 物理")

    return {
        "scenario": "J 班级提示自动消歧",
        "status": "passed",
        "matched_teacher": ti.get("matched_teacher"),
        "disambiguation_note": ti.get("disambiguation_note"),
    }


def check_case_k_request_text_parse(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    rp = result.get("request_parse") or {}
    ti = result.get("teacher_inference") or {}

    ensure(rp.get("auto_parse_used") is True, "K: auto_parse_used should be true")
    ensure(rp.get("teacher") == "李亚", "K: parsed teacher should be 李亚")
    ensure("2504班" in (rp.get("class_hints") or []), "K: class_hints should contain 2504班")
    ensure(rp.get("schedule_type") == "semester", "K: schedule_type should be semester")
    ensure(rp.get("output_format") == "image", "K: output_format should be image")
    ensure(rp.get("send_requested") is False, "K: send_requested should be false")
    ensure(ti.get("matched_teacher") == "李亚琼", "K: should match 李亚琼")
    ensure(ti.get("disambiguation_used") is True, "K: disambiguation_used should be true")
    ensure(result.get("subject") == "物理", "K: subject should be 物理")

    return {
        "scenario": "K 自然语言自动抽取",
        "status": "passed",
        "request_parse": rp,
        "matched_teacher": ti.get("matched_teacher"),
    }


def check_case_l_request_text_week_pdf_send(case: Dict[str, Any]) -> Dict[str, Any]:
    assert_common_success(case)
    result = case["result"]
    rp = result.get("request_parse") or {}
    receipt = result.get("delivery_receipt") or {}

    ensure(result.get("schedule_type") == "week", "L: schedule_type should be week")
    ensure(result.get("week_parity") == "single", "L: week_parity should be single")
    ensure(result.get("output_format") == "pdf", "L: output_format should be pdf")

    ensure(rp.get("schedule_type") == "week", "L: request_parse.schedule_type")
    ensure(rp.get("week_parity") == "single", "L: request_parse.week_parity")
    ensure(rp.get("output_format") == "pdf", "L: request_parse.output_format")
    ensure(rp.get("send_requested") is True, "L: request_parse.send_requested")

    outputs = result.get("outputs") or {}
    ensure(outputs.get("pdf"), "L: outputs.pdf should exist")
    ensure(Path(outputs.get("pdf")).exists(), "L: outputs.pdf file missing")
    ensure(outputs.get("final", "").endswith(".pdf"), "L: outputs.final should be pdf")

    send_status = receipt.get("send_status") or {}
    ensure(send_status.get("state") == "success", "L: send_status.state should be success")
    ensure(send_status.get("success") is True, "L: send_status.success should be true")
    ensure(send_status.get("message_id"), "L: send_status.message_id required")

    return {
        "scenario": "L 自然语言周课表+PDF+发送",
        "status": "passed",
        "request_parse": rp,
        "outputs": {
            "final": outputs.get("final"),
            "pdf": outputs.get("pdf"),
        },
        "send_status": send_status,
    }


def run_all() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    zero_hit_teacher_index = create_zero_hit_teacher_index_override()
    ambiguity_teacher_allocation = create_ambiguity_teacher_allocation()
    ambiguity_teacher_index = create_ambiguity_teacher_index_override()

    plan = [
        {
            "id": "A_priority_success",
            "runner": lambda: run_case(
                "case-a-priority-success",
                [
                    "--teacher",
                    "吕晓瑞",
                    "--diff-summary-path",
                    "data/schedules/catalog/diff-high2-vs-semantic.json",
                ],
            ),
            "checker": check_case_a,
        },
        {
            "id": "B_fallback_no_selfstudy",
            "runner": lambda: run_case("case-b-fallback-no-selfstudy", ["--teacher", "李亚琼"]),
            "checker": check_case_b,
        },
        {
            "id": "C_name_tolerance",
            "runner": lambda: run_case("case-c-name-tolerance", ["--teacher", "吕晓"]),
            "checker": check_case_c,
        },
        {
            "id": "D_zero_hit_failure",
            "runner": lambda: run_case(
                "case-d-zero-hit-failure",
                [
                    "--teacher",
                    "霍卫红",
                    "--teacher-index-json",
                    str(zero_hit_teacher_index.relative_to(ROOT)),
                ],
                expect_rc=1,
            ),
            "checker": check_case_d,
        },
        {
            "id": "E_send_success",
            "runner": lambda: run_case(
                "case-e-send-success",
                ["--teacher", "吕晓瑞", "--send", "--receive-id", SUCCESS_OPEN_ID, "--receive-id-type", "open_id", "--as-image"],
            ),
            "checker": check_case_e,
        },
        {
            "id": "F_not_send",
            "runner": lambda: run_case("case-f-not-send", ["--teacher", "霍卫红"]),
            "checker": check_case_f,
        },
        {
            "id": "G_send_fail",
            "runner": lambda: run_case(
                "case-g-send-fail",
                ["--teacher", "李亚琼", "--send", "--receive-id", INVALID_OPEN_ID, "--receive-id-type", "open_id", "--as-image"],
            ),
            "checker": check_case_g,
        },
        {
            "id": "H_current_sheet_scope",
            "runner": lambda: run_case("case-h-current-sheet-scope", ["--teacher", "樊丰丽"]),
            "checker": check_case_h_current_sheet_scope,
        },
        {
            "id": "I_name_ambiguity",
            "runner": lambda: run_case(
                "case-i-name-ambiguity",
                [
                    "--teacher",
                    "李亚",
                    "--teacher-allocation-json",
                    str(ambiguity_teacher_allocation.relative_to(ROOT)),
                    "--teacher-index-json",
                    str(ambiguity_teacher_index.relative_to(ROOT)),
                ],
                expect_rc=1,
            ),
            "checker": check_case_i_name_ambiguity,
        },
        {
            "id": "J_hint_disambiguation",
            "runner": lambda: run_case(
                "case-j-hint-disambiguation",
                [
                    "--teacher",
                    "李亚",
                    "--class-hint",
                    "2504班",
                    "--teacher-allocation-json",
                    str(ambiguity_teacher_allocation.relative_to(ROOT)),
                ],
            ),
            "checker": check_case_j_hint_disambiguation,
        },
        {
            "id": "K_request_text_parse",
            "runner": lambda: run_case(
                "case-k-request-text-parse",
                [
                    "--request-text",
                    "给我李亚2504班的学期课表",
                    "--teacher-allocation-json",
                    str(ambiguity_teacher_allocation.relative_to(ROOT)),
                ],
            ),
            "checker": check_case_k_request_text_parse,
        },
        {
            "id": "L_request_text_week_pdf_send",
            "runner": lambda: run_case(
                "case-l-request-text-week-pdf-send",
                [
                    "--request-text",
                    "给我李亚琼单周周课表PDF并发我",
                    "--teacher-allocation-json",
                    str(ambiguity_teacher_allocation.relative_to(ROOT)),
                    "--send",
                    "--receive-id",
                    SUCCESS_OPEN_ID,
                    "--receive-id-type",
                    "open_id",
                    "--send-pdf-as-file",
                ],
            ),
            "checker": check_case_l_request_text_week_pdf_send,
        },
    ]

    for item in plan:
        case_id = item["id"]
        try:
            case = item["runner"]()
            summary = item["checker"](case)
            cases.append(
                {
                    "id": case_id,
                    "status": "passed",
                    "summary": summary,
                    "artifacts": {
                        "json": case["result"]["outputs"]["json"],
                        "summary": case["result"]["outputs"]["summary"],
                        "image": case["result"]["outputs"]["image"],
                        "pdf": case["result"]["outputs"].get("pdf", ""),
                        "final": case["result"]["outputs"].get("final", ""),
                    },
                }
            )
        except Exception as exc:  # noqa: BLE001
            cases.append(
                {
                    "id": case_id,
                    "status": "failed",
                    "error": {
                        "type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                }
            )

    passed = sum(1 for c in cases if c["status"] == "passed")
    failed = sum(1 for c in cases if c["status"] == "failed")

    report = {
        "report": "feishu-adapter-integration-regression",
        "legacy_report_name": "p6-system-regression",
        "python": str(PYTHON),
        "build_script": str(BUILD),
        "receipt_script": str(RECEIPT),
        "report_paths": {
            "json": str(REPORT_JSON),
            "text": str(REPORT_TXT),
        },
        "counts": {
            "total": len(cases),
            "passed": passed,
            "failed": failed,
        },
        "cases": cases,
    }
    return report


def render_text(report: Dict[str, Any]) -> str:
    lines = [
        "Feishu adapter 集成回归报告（兼容旧名 P6）",
        f"Python: {report['python']}",
        f"Build script: {report['build_script']}",
        f"Receipt script: {report['receipt_script']}",
        f"统计: total={report['counts']['total']} passed={report['counts']['passed']} failed={report['counts']['failed']}",
        "",
    ]
    for idx, case in enumerate(report["cases"], start=1):
        lines.append(f"{idx}. {case['id']} => {case['status']}")
        if case["status"] == "passed":
            summary = case.get("summary") or {}
            scenario = summary.get("scenario", "")
            if scenario:
                lines.append(f"   场景: {scenario}")
            for key, value in summary.items():
                if key == "scenario":
                    continue
                lines.append(f"   {key}: {json.dumps(value, ensure_ascii=False)}")
            artifacts = case.get("artifacts") or {}
            for key in ("image", "pdf", "final", "json", "summary"):
                if artifacts.get(key):
                    lines.append(f"   {key}: {artifacts[key]}")
        else:
            err = case.get("error") or {}
            lines.append(f"   error: {err.get('type', '')} | {err.get('message', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    report = run_all()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_TXT.write_text(render_text(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["counts"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
