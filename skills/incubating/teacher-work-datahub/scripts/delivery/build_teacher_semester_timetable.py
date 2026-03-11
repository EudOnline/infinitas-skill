#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一站式老师学期课表主流程（P1）

流程：
1) 输入老师名
2) 从 teacher_allocation 推断学科/班级/年级
3) 选择课表源：优先带自习年级课表；若缺班级则回退全校无自习课表
4) 调用学期图生成
5) 产出结构化结果 JSON + 文本摘要

说明：
- 严格不猜测；若 teacher_allocation 找不到老师则直接失败。
- 允许 teacher_allocation 路径传 allgrades 版本，以覆盖高一/高二/高三。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
QUERY_DIR = SCRIPT_DIR.parent / "query"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))
if str(QUERY_DIR) not in sys.path:
    sys.path.insert(0, str(QUERY_DIR))

from delivery_receipt import build_delivery_receipt, render_delivery_receipt_text
from schedule_helpers import (
    TeacherInference,
    choose_primary_subject,
    collect_classes,
    compare_class_sets,
    compute_subject_hit_count,
    extract_schedule_map,
    infer_teacher_classes_subjects,
    load_json,
    map_grade_label_to_title,
    parse_teacher_request_text,
    resolve_source_trace,
    schedule_has_class,
    schedule_has_evening_slots,
)

from resolve_teacher_context import resolve_teacher_context  # type: ignore  # noqa: E402
from resolve_active_sources import build_trace_from_active_source, resolve_schedule_json_path  # type: ignore  # noqa: E402
from catalog_utils import datahub_root, read_json as read_json_datahub  # type: ignore  # noqa: E402


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def choose_python(default_hint: str = "") -> str:
    root = project_root()
    candidates = []
    if default_hint:
        candidates.append(Path(default_hint))
    candidates.extend([
        root / ".venv-schedule" / "bin" / "python",
        root / ".venv" / "bin" / "python",
        Path(sys.executable),
        Path("/usr/bin/python3"),
    ])
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return sys.executable


def teacher_allocation_default_path(root: Path) -> Path:
    candidates = [
        datahub_root() / "curated" / "teacher-allocation" / "teacher_allocation_latest_allgrades.json",
        root / "data" / "schedules" / "teacher_allocation_202603_parsed_allgrades.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def default_output_base(out_dir: Path, teacher: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_teacher = teacher.replace("/", "_").replace(" ", "")
    return str(out_dir / f"教师学期课表-{safe_teacher}-{stamp}")


def unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def choose_schedule_source(
    teacher_name: str,
    classes: List[str],
    subject: str,
    semester: str,
    catalog_json: dict,
    grade_schedule_path: Path,
    school_schedule_path: Path,
    week_parity: str = "all",
    active_sources_json_path: Optional[Path] = None,
) -> dict:
    if active_sources_json_path and active_sources_json_path.exists():
        grade_schedule_path = resolve_schedule_json_path(
            semester=semester,
            kind="grade_schedule_with_selfstudy",
            fallback_path=grade_schedule_path,
            active_sources_json=str(active_sources_json_path),
        )
        school_schedule_path = resolve_schedule_json_path(
            semester=semester,
            kind="school_schedule_no_selfstudy",
            fallback_path=school_schedule_path,
            active_sources_json=str(active_sources_json_path),
        )

    grade_schedule_json = load_json(grade_schedule_path)
    school_schedule_json = load_json(school_schedule_path)

    if active_sources_json_path and active_sources_json_path.exists():
        trace_grade = build_trace_from_active_source(semester, "grade_schedule_with_selfstudy", str(active_sources_json_path))
        trace_school = build_trace_from_active_source(semester, "school_schedule_no_selfstudy", str(active_sources_json_path))
    else:
        trace_grade = resolve_source_trace(catalog_json, semester, "grade_schedule_with_selfstudy")
        trace_school = resolve_source_trace(catalog_json, semester, "school_schedule_no_selfstudy")

    grade_missing = [cls for cls in classes if not schedule_has_class(grade_schedule_json, cls)]
    school_missing = [cls for cls in classes if not schedule_has_class(school_schedule_json, cls)]

    grade_schedule_map = extract_schedule_map(grade_schedule_json, classes)
    school_schedule_map = extract_schedule_map(school_schedule_json, classes)

    grade_hit_count = compute_subject_hit_count(grade_schedule_map, classes, subject, week_parity=week_parity)
    school_hit_count = compute_subject_hit_count(school_schedule_map, classes, subject, week_parity=week_parity)

    if not grade_missing:
        chosen_kind = "grade_schedule_with_selfstudy"
        chosen_path = grade_schedule_path
        chosen_json = grade_schedule_json
        chosen_trace = trace_grade
        chosen_subject_hit_count = grade_hit_count
        fallback_used = False
        fallback_reason = ""
    else:
        if school_missing:
            raise SystemExit(
                f"目标教师 {teacher_name} 的班级在优先源缺失，且回退源仍缺班级："
                f"grade_missing={grade_missing}, school_missing={school_missing}"
            )
        chosen_kind = "school_schedule_no_selfstudy"
        chosen_path = school_schedule_path
        chosen_json = school_schedule_json
        chosen_trace = trace_school
        chosen_subject_hit_count = school_hit_count
        fallback_used = True
        fallback_reason = (
            "优先源缺目标班级，已回退到全校无自习课表："
            + ", ".join(grade_missing)
        )

    chosen_has_evening_slots = schedule_has_evening_slots(chosen_json)
    evening_data_note = (
        "当前课表源包含晚自习节次数据。"
        if chosen_has_evening_slots
        else "当前课表源未提供晚自习节次数据；晚1-晚4 空白不等于无课。"
    )

    return {
        "selected_kind": chosen_kind,
        "selected_path": str(chosen_path),
        "selected_trace": chosen_trace,
        "selected_class_count": len(collect_classes(chosen_json)),
        "selected_subject_hit_count": chosen_subject_hit_count,
        "source_has_evening_slots": chosen_has_evening_slots,
        "evening_data_note": evening_data_note,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "priority_check": {
            "grade_schedule_with_selfstudy": {
                "path": str(grade_schedule_path),
                "trace": trace_grade,
                "missing_classes": grade_missing,
                "subject_hit_count": grade_hit_count,
            },
            "school_schedule_no_selfstudy": {
                "path": str(school_schedule_path),
                "trace": trace_school,
                "missing_classes": school_missing,
                "subject_hit_count": school_hit_count,
            },
        },
    }


def build_summary_text(result: dict) -> str:
    receipt = build_delivery_receipt(result)
    return render_delivery_receipt_text(receipt)


def narrow_class_set_check(class_set_check: Dict[str, Any], classes: List[str]) -> Dict[str, Any]:
    target_classes = set(classes or [])
    if not target_classes:
        return class_set_check
    narrowed_only_in_schedule = sorted([x for x in (class_set_check.get("only_in_schedule") or []) if x in target_classes])
    narrowed_only_in_allocation = sorted([x for x in (class_set_check.get("only_in_allocation") or []) if x in target_classes])
    return {
        **class_set_check,
        "target_class_count": len(target_classes),
        "only_in_schedule": narrowed_only_in_schedule,
        "only_in_allocation": narrowed_only_in_allocation,
    }


def resolve_diff_summary_path(root: Path, diff_summary_path: str) -> str:
    if not diff_summary_path:
        return ""
    path = Path(diff_summary_path).expanduser()
    if not path.is_absolute():
        path = (root / path).resolve()
    return str(path)


def maybe_send_output(
    *,
    send_enabled: bool,
    file_path: Path,
    receive_id: str,
    receive_id_type: str,
    as_image: bool,
) -> Optional[dict]:
    if not send_enabled:
        return None
    raise SystemExit(
        "当前 datahub core 不内置飞书发送；如需发送，请使用 Feishu adapter 层调用。"
    )


def image_to_pdf(image_path: Path, pdf_path: Path) -> Path:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as im:
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        elif im.mode != "RGB":
            im = im.convert("RGB")
        im.save(pdf_path, "PDF", resolution=150.0)
    return pdf_path


def run_image_generator(
    python_bin: str,
    script_path: Path,
    schedule_json: Path,
    classes: List[str],
    title: str,
    subtitle: str,
    subject: str,
    semester_schedule_json: Path,
    out_path: Path,
    source_kind: str,
    source_has_evening_slots: bool,
    week_parity: str = "all",
) -> None:
    cmd = [
        python_bin,
        str(script_path),
        "--schedule-json",
        str(schedule_json),
        "--classes",
        ",".join(classes),
        "--title",
        title,
        "--subtitle",
        subtitle,
        "--subject",
        subject,
        "--semester-schedule-json",
        str(semester_schedule_json),
        "--source-kind",
        source_kind,
        "--source-has-evening-slots",
        "true" if source_has_evening_slots else "false",
    ]
    # 周课表脚本支持 week-parity；学期课表脚本固定单双周同图，忽略该参数
    if "generate_timetable_image.py" in str(script_path):
        cmd.extend(["--week-parity", week_parity])
    cmd.extend(["--out", str(out_path)])
    subprocess.run(cmd, check=True)


def resolve_python_bin(python_bin: str) -> str:
    return choose_python(python_bin)


def teacher_inference_to_dict(inf: TeacherInference) -> dict:
    return {
        "requested_teacher": inf.requested_teacher,
        "matched_teacher": inf.matched_teacher,
        "teacher_fallback_used": inf.teacher_fallback_used,
        "teacher_fallback_note": inf.teacher_fallback_note,
        "subjects": inf.subjects,
        "classes": inf.classes,
        "grade_labels": inf.grade_labels,
        "evidence": inf.evidence,
        "sheet_scope": inf.sheet_scope,
        "sheet_scope_note": inf.sheet_scope_note,
        "ambiguity_detected": inf.ambiguity_detected,
        "ambiguity_note": inf.ambiguity_note,
        "ambiguity_options": inf.ambiguity_options,
        "disambiguation_used": inf.disambiguation_used,
        "disambiguation_note": inf.disambiguation_note,
    }


def request_parse_to_dict(
    parsed: Optional[dict],
    *,
    effective_teacher: str = "",
    effective_class_hint: str = "",
    effective_subject_hint: str = "",
) -> dict:
    base = {
        "request_text": "",
        "teacher": "",
        "class_hints": [],
        "subject_hints": [],
        "schedule_type": "",
        "week_parity": "",
        "output_format": "",
        "send_requested": False,
        "auto_parse_used": False,
        "effective_teacher": effective_teacher,
        "effective_class_hint": effective_class_hint,
        "effective_subject_hint": effective_subject_hint,
    }
    if not parsed:
        return base
    base.update(
        {
            "request_text": parsed.get("request_text", ""),
            "teacher": parsed.get("teacher", ""),
            "class_hints": list(parsed.get("class_hints") or []),
            "subject_hints": list(parsed.get("subject_hints") or []),
            "schedule_type": parsed.get("schedule_type", ""),
            "week_parity": parsed.get("week_parity", ""),
            "output_format": parsed.get("output_format", ""),
            "send_requested": bool(parsed.get("send_requested")),
            "auto_parse_used": bool(parsed.get("auto_parse_used")),
        }
    )
    return base


def build_failure_result(
    *,
    teacher: str,
    out_image: Path,
    out_json: Path,
    out_txt: Path,
    inference: Optional[TeacherInference] = None,
    parsed_request: Optional[dict] = None,
    effective_teacher: str = "",
    effective_class_hint: str = "",
    effective_subject_hint: str = "",
    title: str = "",
    subject: str = "",
    classes: Optional[List[str]] = None,
    selected_source: Optional[Dict[str, Any]] = None,
    send_result: Optional[dict] = None,
    diff_summary_path: str = "",
    class_set_check: Optional[Dict[str, Any]] = None,
    error_type: str = "system_exit",
    error_message: str = "",
) -> dict:
    result = {
        "status": "failed",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "teacher": teacher,
        "request_parse": request_parse_to_dict(
            parsed_request,
            effective_teacher=effective_teacher,
            effective_class_hint=effective_class_hint,
            effective_subject_hint=effective_subject_hint,
        ),
        "teacher_inference": teacher_inference_to_dict(inference)
        if inference is not None
        else {
            "requested_teacher": teacher,
            "matched_teacher": "",
            "teacher_fallback_used": False,
            "teacher_fallback_note": "",
            "subjects": [],
            "classes": [],
            "grade_labels": [],
            "evidence": [],
            "sheet_scope": "",
            "sheet_scope_note": "",
            "ambiguity_detected": False,
            "ambiguity_note": "",
            "ambiguity_options": [],
            "disambiguation_used": False,
            "disambiguation_note": "",
        },
        "subject": subject,
        "classes": list(classes or []),
        "title": title,
        "selected_source": selected_source or {},
        "outputs": {
            "image": str(out_image),
            "json": str(out_json),
            "summary": str(out_txt),
        },
        "send_result": send_result,
        "diff_summary_path": diff_summary_path,
        "class_set_check": class_set_check or {},
        "error": {
            "type": error_type,
            "message": error_message,
        },
    }
    receipt = build_delivery_receipt(result)
    result["delivery_receipt"] = receipt
    summary_text = render_delivery_receipt_text(receipt)
    result["summary_text"] = summary_text
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    out_txt.write_text(summary_text + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", default="", help="教师姓名")
    parser.add_argument("--request-text", default="", help="自然语言请求文本；可自动抽取老师/班级/学科提示")
    parser.add_argument("--preferred-subject", default="", help="可选：优先学科")
    parser.add_argument("--class-hint", default="", help="可选：用于消歧的班级提示，如 2504班")
    parser.add_argument("--subject-hint", default="", help="可选：用于消歧的学科提示，如 物理")
    parser.add_argument("--schedule-type", choices=["semester", "week"], default="semester", help="课表类型：semester|week")
    parser.add_argument("--week-parity", choices=["single", "double", "all"], default="all", help="周课表单双周口径")
    parser.add_argument("--output-format", choices=["image", "pdf"], default="image", help="输出格式：image|pdf")
    parser.add_argument("--semester", default="S2", help="学期代码，默认 S2")
    parser.add_argument(
        "--teacher-allocation-json",
        default="",
        help="教师配备表解析 JSON；默认优先读 datahub curated latest allgrades",
    )
    parser.add_argument(
        "--teacher-index-json",
        default="data/teacher-work-datahub/curated/indexes/teacher_index.json",
        help="统一教师索引 JSON（优先于 teacher_allocation 推断）",
    )
    parser.add_argument(
        "--catalog-json",
        default="data/schedules/catalog/sources.json",
        help="课表源台账 JSON（兼容旧逻辑）",
    )
    parser.add_argument(
        "--active-sources-json",
        default="data/teacher-work-datahub/curated/indexes/active_sources.json",
        help="datahub active sources JSON（优先用于课表源解析）",
    )
    parser.add_argument(
        "--grade-schedule-json",
        default="data/schedules/2025-2026-S2-grade10cohort2024-grade11-complete.json",
        help="带自习年级课表 JSON",
    )
    parser.add_argument(
        "--school-schedule-json",
        default="data/schedules/school_schedule_2025_2026S2_latest.json",
        help="全校无自习课表 JSON",
    )
    parser.add_argument(
        "--semester-schedule-json",
        default="config/semester_schedule.json",
        help="官方作息 JSON",
    )
    parser.add_argument(
        "--generator-script",
        default="",
        help="可选：出图脚本路径；默认按 schedule_type 自动选择",
    )
    parser.add_argument(
        "--python-bin",
        default="",
        help="用于调用出图脚本的 Python；默认自动探测可用环境",
    )
    parser.add_argument(
        "--out-base",
        default="",
        help="输出路径基名（不带后缀）；默认自动按时间戳生成",
    )
    parser.add_argument("--send", action="store_true", help="成功生成后自动发送到飞书")
    parser.add_argument("--receive-id", default="", help="飞书接收方 ID")
    parser.add_argument("--receive-id-type", default="open_id", help="飞书接收方 ID 类型")
    parser.add_argument("--as-image", action="store_true", help="按图片发送；默认按文件发送")
    parser.add_argument("--send-pdf-as-file", action="store_true", help="当输出为 PDF 时，以文件消息发送")
    parser.add_argument(
        "--diff-summary-path",
        default="",
        help="可选：版本差异摘要 JSON 路径，用于写入结果与回执",
    )
    args = parser.parse_args()

    root = project_root()
    teacher_allocation_path = (
        Path(args.teacher_allocation_json).expanduser().resolve()
        if args.teacher_allocation_json
        else teacher_allocation_default_path(root)
    )
    teacher_index_path = (root / args.teacher_index_json).resolve()
    active_sources_path = (root / args.active_sources_json).resolve()
    catalog_path = (root / args.catalog_json).resolve()
    grade_schedule_path = (root / args.grade_schedule_json).resolve()
    school_schedule_path = (root / args.school_schedule_json).resolve()
    semester_schedule_path = (root / args.semester_schedule_json).resolve()

    out_dir = root / "data" / "reports" / "teacher-semester-flow"
    out_dir.mkdir(parents=True, exist_ok=True)

    teacher_allocation_json = load_json(teacher_allocation_path)
    catalog_json = load_json(catalog_path)
    diff_summary_path = resolve_diff_summary_path(root, args.diff_summary_path)

    parsed_request: Optional[dict] = None
    effective_teacher = args.teacher.strip()
    effective_class_hint = args.class_hint.strip()
    effective_subject_hint = args.subject_hint.strip()
    effective_schedule_type = args.schedule_type
    effective_week_parity = args.week_parity
    effective_output_format = args.output_format
    effective_send = bool(args.send)

    if args.request_text.strip():
        parsed_request = parse_teacher_request_text(teacher_allocation_json, args.request_text.strip())
        if not effective_teacher:
            effective_teacher = parsed_request.get("teacher", "")
        if not effective_class_hint and parsed_request.get("class_hints"):
            effective_class_hint = ",".join(parsed_request.get("class_hints") or [])
        if not effective_subject_hint and parsed_request.get("subject_hints"):
            effective_subject_hint = ",".join(parsed_request.get("subject_hints") or [])

        parsed_schedule_type = parsed_request.get("schedule_type") or ""
        if parsed_schedule_type in {"semester", "week"} and args.schedule_type == "semester":
            effective_schedule_type = parsed_schedule_type

        parsed_week_parity = parsed_request.get("week_parity") or ""
        if parsed_week_parity in {"single", "double", "all"} and args.week_parity == "all":
            effective_week_parity = parsed_week_parity

        parsed_output_format = parsed_request.get("output_format") or ""
        if parsed_output_format in {"image", "pdf"} and args.output_format == "image":
            effective_output_format = parsed_output_format

        # datahub core 仅记录自然语言中的发送意图，不直接执行发送。
        # 实际发送由外部 adapter（如 Feishu adapter）读取 request_parse.send_requested 后处理。

    if effective_schedule_type == "week" and effective_week_parity not in {"single", "double", "all"}:
        effective_week_parity = "all"

    if not effective_teacher:
        raise SystemExit("未能从输入中识别教师姓名；请直接提供老师姓名，或在自然语言中包含更明确的教师姓名。")

    out_base = Path(args.out_base) if args.out_base else Path(default_output_base(out_dir, effective_teacher))
    if not out_base.is_absolute():
        out_base = (root / out_base).resolve()
    out_image = out_base.with_suffix(".jpg")
    out_pdf = out_base.with_suffix(".pdf")
    out_json = out_base.with_suffix(".json")
    out_txt = out_base.with_suffix(".txt")

    inference: Optional[TeacherInference] = None
    classes: List[str] = []
    subject = ""
    title = ""
    selected_source: Optional[dict] = None
    send_result: Optional[dict] = None
    class_set_check: Dict[str, Any] = {}

    try:
        explicit_classes = [x.strip() for x in effective_class_hint.split(",") if x.strip()]
        explicit_subjects = [x.strip() for x in effective_subject_hint.split(",") if x.strip()]
        teacher_ctx = resolve_teacher_context(
            teacher=effective_teacher,
            explicit_classes=explicit_classes,
            explicit_subjects=explicit_subjects,
            teacher_index_json=str(teacher_index_path),
        )
        if teacher_ctx:
            if teacher_ctx.get("ambiguity_detected"):
                inference = TeacherInference(
                    requested_teacher=effective_teacher,
                    matched_teacher=teacher_ctx.get("teacher") or "",
                    teacher_fallback_used=False,
                    teacher_fallback_note="",
                    subjects=list(teacher_ctx.get("subjects") or []),
                    classes=list(teacher_ctx.get("classes") or []),
                    grade_labels=list(teacher_ctx.get("grades") or []),
                    evidence=list(teacher_ctx.get("evidence") or []),
                    sheet_scope=teacher_ctx.get("sheet_scope") or (teacher_ctx.get("source") or "teacher_index"),
                    sheet_scope_note=teacher_ctx.get("sheet_scope_note") or "",
                    ambiguity_detected=True,
                    ambiguity_note=teacher_ctx.get("ambiguity_note") or f"教师名存在歧义：{effective_teacher}",
                    ambiguity_options=list(teacher_ctx.get("ambiguity_options") or []),
                    disambiguation_used=bool(teacher_ctx.get("disambiguation_used")),
                    disambiguation_note=teacher_ctx.get("disambiguation_note") or "",
                )
            else:
                matched_teacher = teacher_ctx.get("teacher") or effective_teacher
                inferred_classes = unique_keep_order(list(teacher_ctx.get("classes") or []))
                inferred_subjects = list(teacher_ctx.get("subjects") or [])
                inferred_grades = list(teacher_ctx.get("grades") or [])
                source_name = teacher_ctx.get("source") or "teacher_index"
                source_note = teacher_ctx.get("sheet_scope_note") or {
                    "explicit": "优先使用显式班级/学科输入。",
                    "user_override": "优先使用用户 override 口径。",
                    "teacher_index": "优先使用统一 teacher_index 解析老师上下文。",
                }.get(source_name, "使用统一老师上下文解析结果。")
                tolerance_note = teacher_ctx.get("disambiguation_note") or (f"已按容错名处理：{effective_teacher} -> {matched_teacher}" if matched_teacher != effective_teacher else "")
                inference = TeacherInference(
                    requested_teacher=effective_teacher,
                    matched_teacher=matched_teacher,
                    teacher_fallback_used=matched_teacher != effective_teacher,
                    teacher_fallback_note=tolerance_note,
                    subjects=inferred_subjects,
                    classes=inferred_classes,
                    grade_labels=inferred_grades,
                    evidence=list(teacher_ctx.get("evidence") or []),
                    sheet_scope=teacher_ctx.get("sheet_scope") or source_name,
                    sheet_scope_note=source_note,
                    ambiguity_detected=bool(teacher_ctx.get("ambiguity_detected")),
                    ambiguity_note=teacher_ctx.get("ambiguity_note") or "",
                    ambiguity_options=list(teacher_ctx.get("ambiguity_options") or []),
                    disambiguation_used=bool(teacher_ctx.get("disambiguation_used")),
                    disambiguation_note=teacher_ctx.get("disambiguation_note") or "",
                )
        else:
            inference = infer_teacher_classes_subjects(
                teacher_allocation_json,
                effective_teacher,
                class_hint=effective_class_hint,
                subject_hint=effective_subject_hint,
            )
        if inference.ambiguity_detected:
            raise SystemExit(inference.ambiguity_note or f"教师名存在歧义：{effective_teacher}")
        if not inference.matched_teacher or not inference.classes or not inference.subjects:
            raise SystemExit(f"未能从 teacher_allocation / teacher_index 推断老师信息：{effective_teacher}")

        classes = unique_keep_order(inference.classes)
        subject = choose_primary_subject(inference.subjects, preferred=args.preferred_subject)
        if not subject:
            raise SystemExit(f"未能确定老师学科：{effective_teacher}")

        if not inference.grade_labels:
            inferred_grade_labels = []
            for cls in classes:
                raw_cls = cls.replace("班", "")
                if raw_cls.startswith("24") and "高二" not in inferred_grade_labels:
                    inferred_grade_labels.append("高二")
                elif raw_cls.startswith("25") and "高三" not in inferred_grade_labels:
                    inferred_grade_labels.append("高三")
                elif raw_cls.startswith("23") and "高一" not in inferred_grade_labels:
                    inferred_grade_labels.append("高一")
            if inferred_grade_labels:
                inference.grade_labels = inferred_grade_labels

        title = map_grade_label_to_title(inference.grade_labels)

        selected_source = choose_schedule_source(
            teacher_name=effective_teacher,
            classes=classes,
            subject=subject,
            semester=args.semester,
            catalog_json=catalog_json,
            grade_schedule_path=grade_schedule_path,
            school_schedule_path=school_schedule_path,
            week_parity=effective_week_parity,
            active_sources_json_path=active_sources_path,
        )

        selected_subject_hit_count = int(selected_source.get("selected_subject_hit_count") or 0)
        selected_schedule_json = load_json(Path(selected_source["selected_path"]))
        class_set_check = narrow_class_set_check(compare_class_sets(selected_schedule_json, teacher_allocation_json), classes)
        if selected_subject_hit_count <= 0:
            raise SystemExit(
                "质量门禁失败："
                f"老师 {inference.matched_teacher or effective_teacher} 在已选课表源 "
                f"{selected_source.get('selected_kind', '')} 的结果命中数为0，停止出图。"
            )

        generator_script_path = (
            (root / args.generator_script).resolve()
            if args.generator_script
            else (
                root / "skills" / "teacher-work-datahub" / "scripts" / "delivery" /
                ("generate_timetable_image.py" if effective_schedule_type == "week" else "generate_semester_timetable_image.py")
            ).resolve()
        )

        display_week_parity = effective_week_parity if effective_schedule_type == "week" else "all"

        run_image_generator(
            python_bin=resolve_python_bin(args.python_bin),
            script_path=generator_script_path,
            schedule_json=Path(selected_source["selected_path"]),
            classes=classes,
            title=title,
            subtitle=inference.matched_teacher or effective_teacher,
            subject=subject,
            semester_schedule_json=semester_schedule_path,
            out_path=out_image,
            source_kind=selected_source["selected_kind"],
            source_has_evening_slots=selected_source["source_has_evening_slots"],
            week_parity=display_week_parity,
        )

        final_output_path = out_image
        final_as_image = bool(args.as_image)
        if effective_output_format == "pdf":
            image_to_pdf(out_image, out_pdf)
            final_output_path = out_pdf
            final_as_image = False if (args.send_pdf_as_file or not args.as_image) else True

        send_result = maybe_send_output(
            send_enabled=effective_send,
            file_path=final_output_path,
            receive_id=args.receive_id,
            receive_id_type=args.receive_id_type,
            as_image=final_as_image,
        )

        result = {
            "status": "success",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "teacher": effective_teacher,
            "request_parse": request_parse_to_dict(
                parsed_request,
                effective_teacher=effective_teacher,
                effective_class_hint=effective_class_hint,
                effective_subject_hint=effective_subject_hint,
            ),
            "schedule_type": effective_schedule_type,
            "week_parity": effective_week_parity,
            "output_format": effective_output_format,
            "teacher_inference": teacher_inference_to_dict(inference),
            "subject": subject,
            "classes": classes,
            "title": title,
            "selected_source": selected_source,
            "class_set_check": class_set_check,
            "diff_summary_path": diff_summary_path,
            "outputs": {
                "image": str(out_image),
                "pdf": str(out_pdf) if out_pdf.exists() else "",
                "final": str(final_output_path),
                "json": str(out_json),
                "summary": str(out_txt),
            },
            "send_result": send_result,
        }
        receipt = build_delivery_receipt(result)
        result["delivery_receipt"] = receipt
        summary_text = render_delivery_receipt_text(receipt)
        result["summary_text"] = summary_text

        out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        out_txt.write_text(summary_text + "\n", encoding="utf-8")

        print(json.dumps(result, ensure_ascii=False, indent=2))
    except SystemExit as exc:
        error_message = str(exc)
        failed_result = build_failure_result(
            teacher=effective_teacher,
            out_image=out_image,
            out_json=out_json,
            out_txt=out_txt,
            inference=inference,
            parsed_request=parsed_request,
            effective_teacher=effective_teacher,
            effective_class_hint=effective_class_hint,
            effective_subject_hint=effective_subject_hint,
            title=title,
            subject=subject,
            classes=classes,
            selected_source=selected_source,
            send_result=send_result,
            diff_summary_path=diff_summary_path,
            class_set_check=class_set_check,
            error_type="system_exit",
            error_message=error_message,
        )
        print(json.dumps(failed_result, ensure_ascii=False, indent=2))
        raise


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"出图脚本执行失败：{e}", file=sys.stderr)
        raise
