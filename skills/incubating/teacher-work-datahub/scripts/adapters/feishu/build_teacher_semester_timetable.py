#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Feishu adapter wrapper: 调用 teacher-work-datahub core，再按需要发送到飞书。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from send_timetable_feishu import send_timetable_file

ROOT = Path(__file__).resolve().parents[5]
CORE_BUILD = ROOT / "skills" / "teacher-work-datahub" / "scripts" / "delivery" / "build_teacher_semester_timetable.py"
PYTHON = Path(sys.executable).resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", default="", help="教师姓名")
    parser.add_argument("--request-text", default="", help="自然语言请求文本；可自动抽取老师/班级/学科提示")
    parser.add_argument("--preferred-subject", default="", help="可选：优先学科")
    parser.add_argument("--class-hint", default="", help="可选：用于消歧的班级提示，如 2504班")
    parser.add_argument("--subject-hint", default="", help="可选：用于消歧的学科提示，如 物理")
    parser.add_argument("--schedule-type", choices=["semester", "week"], default="semester")
    parser.add_argument("--week-parity", choices=["single", "double", "all"], default="all")
    parser.add_argument("--output-format", choices=["image", "pdf"], default="image")
    parser.add_argument("--semester", default="S2")
    parser.add_argument("--teacher-allocation-json", default="")
    parser.add_argument("--teacher-index-json", default="")
    parser.add_argument("--schedule-json", default="")
    parser.add_argument("--school-schedule-json", default="")
    parser.add_argument("--active-sources-json", default="")
    parser.add_argument("--slot-time-json", default="")
    parser.add_argument("--diff-summary-path", default="")
    parser.add_argument("--font-path", default="")
    parser.add_argument("--python-bin", default="", help="兼容旧参数：adapter 层忽略，实际以当前 Python 调用 datahub core")
    parser.add_argument("--out-base", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--receive-id", default="")
    parser.add_argument("--receive-id-type", default="open_id")
    parser.add_argument("--as-image", action="store_true")
    parser.add_argument("--send-pdf-as-file", action="store_true")
    parser.add_argument("--allow-teacher-fallback", action="store_true")
    args = parser.parse_args()

    core_cmd = [str(PYTHON), str(CORE_BUILD)]
    send_requested_via_text = False
    passthrough = {
        "--teacher": args.teacher,
        "--request-text": args.request_text,
        "--preferred-subject": args.preferred_subject,
        "--class-hint": args.class_hint,
        "--subject-hint": args.subject_hint,
        "--schedule-type": args.schedule_type,
        "--week-parity": args.week_parity,
        "--output-format": args.output_format,
        "--semester": args.semester,
        "--teacher-allocation-json": args.teacher_allocation_json,
        "--teacher-index-json": args.teacher_index_json,
        "--schedule-json": args.schedule_json,
        "--school-schedule-json": args.school_schedule_json,
        "--active-sources-json": args.active_sources_json,
        "--slot-time-json": args.slot_time_json,
        "--diff-summary-path": args.diff_summary_path,
        "--font-path": args.font_path,
        "--out-base": args.out_base,
        "--out-dir": args.out_dir,
    }
    for k, v in passthrough.items():
        if v:
            core_cmd.extend([k, v])
    if args.allow_teacher_fallback:
        core_cmd.append("--allow-teacher-fallback")

    proc = subprocess.run(core_cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode

    stdout = proc.stdout.strip()
    if not stdout:
        raise SystemExit("datahub core 未返回结果")
    lines = [line for line in stdout.splitlines() if line.strip()]
    json_text = "\n".join(lines[1:]) if lines and lines[0].lower().endswith((".jpg", ".pdf", ".png")) else stdout
    result = json.loads(json_text)

    request_parse = result.get("request_parse") or {}
    send_requested_via_text = bool(request_parse.get("send_requested"))

    send_result = None
    if args.send or send_requested_via_text:
        outputs = result.get("outputs") or {}
        final_path = (outputs.get("final") or outputs.get("image") or "")
        if (result.get("output_format") == "pdf" or request_parse.get("output_format") == "pdf") and outputs.get("pdf"):
            final_path = outputs.get("pdf")
        if not final_path:
            raise SystemExit("adapter 发送失败：未找到可发送输出文件")
        use_image = bool(args.as_image)
        effective_output_format = result.get("output_format") or request_parse.get("output_format") or args.output_format
        if effective_output_format == "pdf" and args.send_pdf_as_file:
            use_image = False
        send_result = send_timetable_file(
            file_path=final_path,
            receive_id=args.receive_id,
            receive_id_type=args.receive_id_type,
            as_image=use_image,
        )
        result["send_result"] = send_result
        try:
            from skills.teacher_work_datahub.scripts.delivery.delivery_receipt import build_delivery_receipt, render_delivery_receipt_text  # type: ignore
        except Exception:
            sys.path.insert(0, str(ROOT / "skills" / "teacher-work-datahub" / "scripts" / "delivery"))
            from delivery_receipt import build_delivery_receipt, render_delivery_receipt_text  # type: ignore
        result["delivery_receipt"] = build_delivery_receipt(result)
        result["summary_text"] = render_delivery_receipt_text(result["delivery_receipt"])
        json_path = Path((result.get("outputs") or {}).get("json", ""))
        summary_path = Path((result.get("outputs") or {}).get("summary", ""))
        if json_path:
            json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if summary_path:
            summary_path.write_text(result["summary_text"] + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
