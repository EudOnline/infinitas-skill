#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准交付回执构造辅助。

职责：
1) 从 build_teacher_semester_timetable 的结果 JSON 中抽取标准字段
2) 统一归一化发送状态（success / failed / not_sent）
3) 输出稳定的回执 JSON 结构与文本摘要
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional


JsonDict = Dict[str, Any]


def _s(value: Any) -> str:
    return "" if value is None else str(value)


def _json_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def summarize_send_error(error: Optional[JsonDict]) -> str:
    if not error:
        return "—"
    err_type = _s(error.get("type"))
    message = _s(error.get("message"))
    parts = [part for part in [err_type, message] if part]
    return " | ".join(parts) if parts else "unknown_error"


def normalize_send_status(send_result: Optional[JsonDict]) -> JsonDict:
    if send_result is None:
        return {
            "state": "not_sent",
            "requested": False,
            "success": None,
            "method": "",
            "message_id": "",
            "error_summary": "未发送",
            "error": None,
        }

    success = bool(send_result.get("success"))
    return {
        "state": "success" if success else "failed",
        "requested": True,
        "success": success,
        "method": _s(send_result.get("method")),
        "message_id": _s(send_result.get("message_id")),
        "error_summary": "—" if success else summarize_send_error(send_result.get("error")),
        "error": send_result.get("error"),
    }


def normalize_generation_status(result: JsonDict) -> JsonDict:
    generation_success = _s(result.get("status")) == "success"
    return {
        "state": "success" if generation_success else "failed",
        "success": generation_success,
    }



def determine_overall_status(generation_status: JsonDict, send_status: JsonDict) -> str:
    if not generation_status.get("success"):
        return "failed"
    if send_status.get("requested") and not send_status.get("success"):
        return "partial_success"
    return "success"



def build_delivery_receipt(result: JsonDict) -> JsonDict:
    teacher_inference = result.get("teacher_inference") or {}
    selected_source = result.get("selected_source") or {}
    selected_trace = selected_source.get("selected_trace") or {}
    outputs = result.get("outputs") or {}
    send_status = normalize_send_status(result.get("send_result"))
    generation_status = normalize_generation_status(result)
    overall_status = determine_overall_status(generation_status, send_status)
    error = result.get("error") or {}
    class_set_check = result.get("class_set_check") or {}

    teacher_requested = _s(teacher_inference.get("requested_teacher") or result.get("teacher"))
    teacher_matched = _s(teacher_inference.get("matched_teacher"))
    teacher_note = _s(teacher_inference.get("teacher_fallback_note"))
    teacher_fallback_used = bool(teacher_inference.get("teacher_fallback_used"))

    fallback_used = bool(selected_source.get("fallback_used"))
    fallback_note = _s(selected_source.get("fallback_reason"))

    receipt = {
        "result_status": _s(result.get("status")),
        "generation_status": generation_status,
        "overall_status": overall_status,
        "teacher": {
            "requested": teacher_requested,
            "matched": teacher_matched,
        },
        "subject": _s(result.get("subject")),
        "classes": list(result.get("classes") or []),
        "title": _s(result.get("title")),
        "output_file_paths": {
            "image": _s(outputs.get("image")),
            "pdf": _s(outputs.get("pdf")),
            "final": _s(outputs.get("final") or outputs.get("image")),
            "json": _s(outputs.get("json")),
            "summary": _s(outputs.get("summary")),
        },
        "send_status": send_status,
        "source_trace": {
            "kind": _s(selected_trace.get("kind")),
            "active_record_id": _s(selected_trace.get("record_id")),
            "source_name": _s(selected_trace.get("source_name")),
            "archived_path": _s(selected_trace.get("archived_path")),
            "status": _s(selected_trace.get("status")),
        },
        "teacher_name_tolerance": {
            "used": teacher_fallback_used,
            "requested_name": teacher_requested,
            "matched_name": teacher_matched,
            "note": teacher_note,
        },
        "fallback": {
            "used": fallback_used,
            "note": fallback_note,
        },
        "selected_source": {
            "kind": _s(selected_source.get("selected_kind")),
            "path": _s(selected_source.get("selected_path")),
            "has_evening_slots": bool(selected_source.get("source_has_evening_slots")),
            "evening_data_note": _s(selected_source.get("evening_data_note")),
        },
        "class_set_check": {
            "schedule_class_count": int(class_set_check.get("schedule_class_count") or 0),
            "allocation_class_count": int(class_set_check.get("allocation_class_count") or 0),
            "only_in_schedule": list(class_set_check.get("only_in_schedule") or []),
            "only_in_allocation": list(class_set_check.get("only_in_allocation") or []),
        },
        "error": {
            "type": _s(error.get("type")),
            "message": _s(error.get("message")),
        },
        "diff_summary_path": _s(result.get("diff_summary_path") or outputs.get("diff_json")),
    }
    return receipt


def render_delivery_receipt_text(receipt: JsonDict) -> str:
    teacher = receipt.get("teacher") or {}
    generation_status = receipt.get("generation_status") or {}
    send_status = receipt.get("send_status") or {}
    source_trace = receipt.get("source_trace") or {}
    tolerance = receipt.get("teacher_name_tolerance") or {}
    fallback = receipt.get("fallback") or {}
    selected_source = receipt.get("selected_source") or {}
    class_set_check = receipt.get("class_set_check") or {}
    output_file_paths = receipt.get("output_file_paths") or {}

    send_state_label_map = {
        "success": "已发送",
        "failed": "发送失败",
        "not_sent": "未发送",
    }
    send_state = _s(send_status.get("state"))
    send_state_label = send_state_label_map.get(send_state, send_state or "未知")

    overall_status = _s(receipt.get("overall_status"))
    overall_status_label_map = {
        "success": "成功",
        "partial_success": "部分成功",
        "failed": "失败",
    }
    overall_status_label = overall_status_label_map.get(overall_status, overall_status or "未知")

    generation_state = _s(generation_status.get("state"))
    generation_state_label_map = {
        "success": "生成成功",
        "failed": "生成失败",
    }
    generation_state_label = generation_state_label_map.get(generation_state, generation_state or "未知")

    teacher_requested = _s(teacher.get("requested"))
    teacher_matched = _s(teacher.get("matched"))
    teacher_line = f"教师：{teacher_requested}"
    if teacher_matched:
        teacher_line += f"（匹配：{teacher_matched}）"

    classes = receipt.get("classes") or []
    classes_text = ", ".join(classes) if classes else ""

    tolerance_note = _s(tolerance.get("note")) if tolerance.get("used") else "未触发"
    fallback_note = _s(fallback.get("note")) if fallback.get("used") else "未触发"

    lines = [
        f"结果状态：{_s(receipt.get('result_status'))}",
        f"整体状态：{overall_status}（{overall_status_label}）",
        f"生成状态：{generation_state}（{generation_state_label}） | success={_json_scalar(generation_status.get('success'))}",
        teacher_line,
        f"学科：{_s(receipt.get('subject'))}",
        f"班级：{classes_text}",
        f"年级标题：{_s(receipt.get('title'))}",
        f"课表源：{_s(selected_source.get('kind'))} | {_s(selected_source.get('path'))}",
        (
            "数据源追溯："
            f"kind={_s(source_trace.get('kind'))} | "
            f"active_record_id={_s(source_trace.get('active_record_id'))} | "
            f"source_name={_s(source_trace.get('source_name'))}"
        ),
        f"晚自习数据：{'已提供' if selected_source.get('has_evening_slots') else '未提供'}",
        f"晚自习说明：{_s(selected_source.get('evening_data_note'))}",
        f"回退说明：{fallback_note}",
        (
            "班级集合对照："
            f"schedule_class_count={int(class_set_check.get('schedule_class_count') or 0)} | "
            f"allocation_class_count={int(class_set_check.get('allocation_class_count') or 0)}"
        ),
        f"仅课表存在：{', '.join(class_set_check.get('only_in_schedule') or []) or '—'}",
        f"仅配备表存在：{', '.join(class_set_check.get('only_in_allocation') or []) or '—'}",
        f"输出文件：image={_s(output_file_paths.get('image'))}",
        f"输出文件：pdf={_s(output_file_paths.get('pdf')) or '—'}",
        f"输出文件：final={_s(output_file_paths.get('final'))}",
        f"输出文件：json={_s(output_file_paths.get('json'))}",
        f"输出文件：summary={_s(output_file_paths.get('summary'))}",
        (
            "发送状态："
            f"{send_state_label} | "
            f"success={_json_scalar(send_status.get('success'))} | "
            f"method={_s(send_status.get('method'))} | "
            f"message_id={_s(send_status.get('message_id'))}"
        ),
        f"发送错误摘要：{_s(send_status.get('error_summary'))}",
        f"姓名容错：{tolerance_note}",
        f"diff_summary_path：{_s(receipt.get('diff_summary_path')) or '（空）'}",
    ]

    error = receipt.get("error") or {}
    if error.get("message"):
        lines.append(f"失败原因：{_s(error.get('message'))}")

    diff_summary_path = _s(receipt.get("diff_summary_path"))
    if diff_summary_path:
        lines.append(f"版本差异摘要：{diff_summary_path}")
    else:
        lines.append("版本差异摘要：未提供")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-json", required=True, help="主流程结果 JSON 路径")
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="输出格式",
    )
    args = parser.parse_args()

    result_path = Path(args.result_json).expanduser().resolve()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    receipt = build_delivery_receipt(result)
    if args.format == "json":
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(render_delivery_receipt_text(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
