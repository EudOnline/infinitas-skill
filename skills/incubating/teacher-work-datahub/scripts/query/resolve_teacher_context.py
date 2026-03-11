#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from catalog_utils import datahub_root, read_json  # noqa: E402
from override_utils import get_teacher_override  # noqa: E402


def teacher_index_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "teacher_index.json"


def normalize_teacher_name(value: str) -> str:
    return (value or "").strip().replace("\u3000", "").replace(" ", "")


def normalize_subject_name(value: str) -> str:
    return (value or "").strip().replace(" ", "")


def normalize_class_name(value: str) -> str:
    text = (value or "").strip().replace(" ", "")
    if not text:
        return ""
    return text if text.endswith("班") else f"{text}班"


def normalize_sheet_name(value: str) -> str:
    return (value or "").strip()


def sheet_rank(value: str) -> tuple[int, str]:
    text = normalize_sheet_name(value)
    if re.fullmatch(r"\d{4}\.\d+", text):
        year, month = text.split(".", 1)
        try:
            return (int(year) * 100 + int(month), text)
        except Exception:
            return (0, text)
    return (0, text)


def summarize_teacher_option(name: str, info: dict) -> dict:
    return {
        "matched_teacher": name,
        "classes": list(info.get("classes") or []),
        "subjects": list(info.get("subjects") or []),
        "evidence_count": len(info.get("evidence") or []),
    }


def candidate_match_score(option: dict, class_hints: list[str], subject_hints: list[str]) -> tuple[int, int, int]:
    option_classes = set(option.get("classes") or [])
    option_subjects = set(option.get("subjects") or [])
    class_hit = len(option_classes.intersection(class_hints)) if class_hints else 0
    subject_hit = len(option_subjects.intersection(subject_hints)) if subject_hints else 0
    return (class_hit, subject_hit, -int(option.get("evidence_count") or 0))


def find_teacher_candidates(teacher: str, index_data: dict) -> list[tuple[str, dict]]:
    teachers = index_data.get("teachers") or {}
    target = normalize_teacher_name(teacher)
    out = []
    for name, info in teachers.items():
        clean = normalize_teacher_name(name)
        if clean == target:
            out.append((name, info))
            continue
        if not target:
            continue
        if target in clean:
            out.append((name, info))
    out.sort(key=lambda item: (item[0] != teacher, abs(len(item[0]) - len(teacher)), len(item[0]), item[0]))
    return out


def choose_teacher_candidate(teacher: str, index_data: dict, class_hints: list[str], subject_hints: list[str]) -> tuple[str | None, dict | None, dict]:
    teachers = index_data.get("teachers") or {}
    if teacher in teachers:
        return teacher, teachers[teacher], {
            "ambiguity_detected": False,
            "ambiguity_note": "",
            "ambiguity_options": [],
            "disambiguation_used": False,
            "disambiguation_note": "",
        }

    candidates = find_teacher_candidates(teacher, index_data)
    if not candidates:
        return None, None, {
            "ambiguity_detected": False,
            "ambiguity_note": "",
            "ambiguity_options": [],
            "disambiguation_used": False,
            "disambiguation_note": "",
        }
    if len(candidates) == 1:
        name, info = candidates[0]
        note = ""
        if name != teacher:
            if class_hints or subject_hints:
                hint_parts = []
                if class_hints:
                    hint_parts.append(f"班级={','.join(class_hints)}")
                if subject_hints:
                    hint_parts.append(f"学科={','.join(subject_hints)}")
                note = f"已按提示条件自动消歧：{teacher} -> {name}（{'；'.join(hint_parts)}）"
            else:
                note = f"已按容错名处理：{teacher} -> {name}"
        return name, info, {
            "ambiguity_detected": False,
            "ambiguity_note": "",
            "ambiguity_options": [],
            "disambiguation_used": name != teacher,
            "disambiguation_note": note,
        }

    options = [summarize_teacher_option(name, info) for name, info in candidates[:8]]
    if not class_hints and not subject_hints:
        return None, None, {
            "ambiguity_detected": True,
            "ambiguity_note": f"教师名存在歧义：{teacher} 可匹配 {', '.join(x['matched_teacher'] for x in options)}；请提供更完整姓名或指定班级/学科。",
            "ambiguity_options": options,
            "disambiguation_used": False,
            "disambiguation_note": "",
        }

    scored = [(candidate_match_score(opt, class_hints, subject_hints), opt) for opt in options]
    best_score = max(score for score, _ in scored)
    winners = [opt for score, opt in scored if score == best_score]
    if (best_score[0] > 0 or best_score[1] > 0) and len(winners) == 1:
        matched_name = winners[0]["matched_teacher"]
        info = teachers.get(matched_name)
        hint_parts = []
        if class_hints:
            hint_parts.append(f"班级={','.join(class_hints)}")
        if subject_hints:
            hint_parts.append(f"学科={','.join(subject_hints)}")
        return matched_name, info, {
            "ambiguity_detected": False,
            "ambiguity_note": "",
            "ambiguity_options": options,
            "disambiguation_used": True,
            "disambiguation_note": f"已按提示条件自动消歧：{teacher} -> {matched_name}（{'；'.join(hint_parts)}）",
        }

    hint_bits = []
    if class_hints:
        hint_bits.append(f"班级={','.join(class_hints)}")
    if subject_hints:
        hint_bits.append(f"学科={','.join(subject_hints)}")
    hint_note = f"（已尝试按{'；'.join(hint_bits)}消歧，仍不唯一）" if hint_bits else ""
    return None, None, {
        "ambiguity_detected": True,
        "ambiguity_note": f"教师名存在歧义：{teacher} 可匹配 {', '.join(x['matched_teacher'] for x in options)}；请提供更完整姓名或指定班级/学科。{hint_note}",
        "ambiguity_options": options,
        "disambiguation_used": False,
        "disambiguation_note": "",
    }


def derive_current_sheet(info: dict) -> str:
    evidence = info.get("evidence") or []
    ranks = [sheet_rank(item.get("sheet", "")) for item in evidence if item.get("sheet")]
    if not ranks:
        return ""
    return sorted(ranks)[-1][1]


def class_grade_code(class_name: str) -> str:
    raw = (class_name or "").replace("班", "").strip()
    return raw[:2] if len(raw) >= 2 and raw[:2].isdigit() else ""


def infer_grade_from_classes(classes: list[str]) -> list[str]:
    out: list[str] = []
    for cls in classes:
        code = class_grade_code(cls)
        grade = ""
        if code == "25":
            grade = "高三"
        elif code == "24":
            grade = "高二"
        elif code == "23":
            grade = "高一"
        if grade and grade not in out:
            out.append(grade)
    return out


def shrink_info_to_current_sheet(name: str, info: dict, meta: dict) -> dict:
    evidence = list(info.get("evidence") or [])
    if not evidence:
        return {
            "teacher": name,
            "classes": list(info.get("classes") or []),
            "subjects": list(info.get("subjects") or []),
            "grades": list(info.get("grades") or []),
            "source": "teacher_index",
            "source_record_id": (info.get("active_source") or {}).get("record_id", ""),
            "override_used": False,
            **meta,
            "evidence": evidence,
        }

    current_sheet = derive_current_sheet(info)
    current_evidence = [item for item in evidence if normalize_sheet_name(item.get("sheet", "")) == current_sheet] if current_sheet else evidence
    if not current_evidence:
        current_evidence = evidence

    classes: list[str] = []
    subjects: list[str] = []
    for item in current_evidence:
        cls = normalize_class_name(item.get("class", ""))
        subj = normalize_subject_name(item.get("subject", ""))
        if cls and cls not in classes:
            classes.append(cls)
        if subj and subj not in subjects:
            subjects.append(subj)

    grades = infer_grade_from_classes(classes) or list(info.get("grades") or [])
    note = f"优先使用统一 teacher_index 解析老师上下文，并收敛到当前 sheet：{current_sheet}" if current_sheet else "优先使用统一 teacher_index 解析老师上下文。"
    if meta.get("disambiguation_note"):
        note = f"{note} {meta['disambiguation_note']}"

    return {
        "teacher": name,
        "classes": classes,
        "subjects": subjects,
        "grades": grades,
        "source": "teacher_index",
        "source_record_id": (info.get("active_source") or {}).get("record_id", ""),
        "override_used": False,
        "evidence": current_evidence,
        "sheet_scope": current_sheet,
        "sheet_scope_note": note,
        **meta,
    }


def resolve_teacher_context(
    *,
    teacher: str,
    explicit_classes: list[str] | None = None,
    explicit_subjects: list[str] | None = None,
    teacher_index_json: str = "",
) -> dict | None:
    explicit_classes = [normalize_class_name(x) for x in (explicit_classes or []) if normalize_class_name(x)]
    explicit_subjects = [normalize_subject_name(x) for x in (explicit_subjects or []) if normalize_subject_name(x)]

    if explicit_classes or explicit_subjects:
        index_path = Path(teacher_index_json).expanduser() if teacher_index_json else teacher_index_path()
        index_data = read_json(index_path, default={}) or {}
        name, info, meta = choose_teacher_candidate(teacher, index_data, explicit_classes, explicit_subjects)
        if info:
            ctx = shrink_info_to_current_sheet(name, info, meta)
            if explicit_classes:
                filtered_classes = [c for c in ctx.get("classes") or [] if c in explicit_classes]
                if filtered_classes:
                    ctx["classes"] = filtered_classes
            if explicit_subjects:
                filtered_subjects = [s for s in ctx.get("subjects") or [] if s in explicit_subjects]
                if filtered_subjects:
                    ctx["subjects"] = filtered_subjects
            return ctx
        return {
            "teacher": teacher,
            "classes": explicit_classes,
            "subjects": explicit_subjects,
            "grades": [],
            "source": "explicit",
            "source_record_id": "",
            "override_used": False,
            **meta,
        }

    override = get_teacher_override(teacher)
    if override:
        return {
            "teacher": teacher,
            "classes": list(override.get("classes") or []),
            "subjects": list(override.get("subjects") or []),
            "grades": [],
            "source": "user_override",
            "source_record_id": "",
            "override_used": True,
            "override_note": override.get("note", ""),
            "ambiguity_detected": False,
            "ambiguity_note": "",
            "ambiguity_options": [],
            "disambiguation_used": False,
            "disambiguation_note": "",
        }

    index_path = Path(teacher_index_json).expanduser() if teacher_index_json else teacher_index_path()
    index_data = read_json(index_path, default={}) or {}
    name, info, meta = choose_teacher_candidate(teacher, index_data, explicit_classes, explicit_subjects)
    if info:
        return shrink_info_to_current_sheet(name, info, meta)
    if meta.get("ambiguity_detected"):
        return {
            "teacher": teacher,
            "classes": [],
            "subjects": [],
            "grades": [],
            "source": "teacher_index",
            "source_record_id": "",
            "override_used": False,
            **meta,
        }

    return None
