#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SEMESTER_MAP = {
    "S1": "S1",
    "s1": "S1",
    "第一学期": "S1",
    "上学期": "S1",
    "S2": "S2",
    "s2": "S2",
    "第二学期": "S2",
    "下学期": "S2",
}

SEMESTER_LABELS = {
    "S1": "第一学期",
    "S2": "第二学期",
}

GRADE_SCOPE_MAP = {
    "primary": "primary",
    "小学": "primary",
    "junior": "junior",
    "初中": "junior",
    "highschool": "highschool",
    "高中": "highschool",
}

GRADE_SCOPE_LABELS = {
    "primary": "小学",
    "junior": "初中",
    "highschool": "高中",
}

GRADE_SCOPE_FROM_GRADE = {
    "高一": "highschool",
    "高二": "highschool",
    "高三": "highschool",
    "高中": "highschool",
    "初一": "junior",
    "初二": "junior",
    "初三": "junior",
    "初中": "junior",
}

SUBJECT_KEY_MAP = {
    "语文": "chinese",
    "数学": "math",
    "英语": "english",
    "政治": "politics",
    "历史": "history",
    "物理": "physics",
    "化学": "chemistry",
    "生物": "biology",
    "生物学": "biology",
    "地理": "geography",
    "信息技术": "it",
    "通用技术": "general_technology",
}

SEMANTIC_TYPE_LABELS = {
    "exam_scope": "考试范围",
    "review_plan": "复习安排",
    "advice": "建议性表述",
    "school_defined": "各校自定",
    "unknown": "未知",
}

SOURCE_STATUS_LABELS = {
    "active": "当前有效版本",
    "archived": "历史归档版本",
    "draft": "暂存/待校对版本",
}


def infer_semantic_type_from_text(text: str) -> str:
    t = norm(text)
    if not t:
        return "unknown"
    if t.startswith("建议"):
        return "advice"
    if "各校" in t or "自主安排" in t or "自行安排" in t:
        return "school_defined"
    if "复习" in t or "一轮" in t or "二轮" in t:
        return "review_plan"
    return "exam_scope"


def normalize_scope_text(text: str) -> str:
    t = norm(text)
    if not t:
        return ""
    t = t.replace("；", ";")
    t = t.replace("，", "；")
    t = t.replace(";", "；")
    return t


def split_scope_chapters(text: str) -> list[str]:
    t = normalize_scope_text(text)
    if not t:
        return []
    if infer_semantic_type_from_text(t) != "exam_scope":
        return []
    return [seg.strip() for seg in t.split("；") if seg.strip()]


def norm(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path | str) -> dict:
    p = path if isinstance(path, Path) else Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def normalize_semester(value: str) -> str:
    v = norm(value)
    return SEMESTER_MAP.get(v, v)


def semester_label(value: str) -> str:
    v = normalize_semester(value)
    return SEMESTER_LABELS.get(v, v)


def normalize_grade_scope(value: str) -> str:
    v = norm(value)
    if v in GRADE_SCOPE_MAP:
        return GRADE_SCOPE_MAP[v]
    if v in GRADE_SCOPE_FROM_GRADE:
        return GRADE_SCOPE_FROM_GRADE[v]
    return v


def grade_scope_label(value: str) -> str:
    v = normalize_grade_scope(value)
    return GRADE_SCOPE_LABELS.get(v, v)


def infer_grade_scope_from_grade(value: str) -> str:
    return GRADE_SCOPE_FROM_GRADE.get(norm(value), "")


def subject_key(value: str) -> str:
    v = norm(value)
    return SUBJECT_KEY_MAP.get(v, v)


def subject_matches(item_subject: str, query_subject: str) -> bool:
    q = norm(query_subject)
    if not q:
        return True
    return subject_key(item_subject) == subject_key(q)


def grade_matches(item_grade: str, query_grade: str) -> bool:
    q = norm(query_grade)
    if not q:
        return True
    return norm(item_grade) == q


def semantic_type_label(value: str) -> str:
    return SEMANTIC_TYPE_LABELS.get(norm(value), norm(value) or "未知")


def source_status_label(value: str) -> str:
    return SOURCE_STATUS_LABELS.get(norm(value), norm(value) or "未知")


def build_review_notice(record: dict, data: dict | None = None) -> dict:
    status = norm(record.get("status")) or norm((data or {}).get("source", {}).get("status"))
    needs_review = status == "draft"
    issues = []
    actions = []
    if isinstance(data, dict):
        issues = list((data.get("warnings") or []))
    if needs_review:
        actions = [
            "当前记录为 draft，查询结果仅供参考，需人工复核后再作为最终口径使用",
            "优先核对原图/原表与结构化摘要是否一致",
            "确认无误后再转为 active",
        ]
    return {
        "needs_review": needs_review,
        "status": status,
        "status_label": source_status_label(status),
        "message": "当前命中的是 draft 版本，结果未最终确认，请先人工复核。" if needs_review else "",
        "issues": issues,
        "actions": actions,
    }


def build_scope_node(
    *,
    status: str = "missing",
    semantic_type: str = "unknown",
    raw_text: str = "",
    normalized_text: str = "",
    chapters: list[str] | None = None,
    confidence: Any = None,
    evidence: list[dict] | None = None,
) -> dict:
    return {
        "status": norm(status) or "missing",
        "semantic_type": norm(semantic_type) or "unknown",
        "raw_text": norm(raw_text),
        "normalized_text": norm(normalized_text),
        "chapters": chapters or [],
        "confidence": confidence,
        "evidence": evidence or [],
    }


def coerce_scope_node(value: Any, default_semantic_type: str = "exam_scope") -> dict:
    if isinstance(value, dict):
        chapters = value.get("chapters") or []
        raw_text = norm(value.get("raw_text"))
        normalized_text = norm(value.get("normalized_text"))
        if not raw_text and normalized_text:
            raw_text = normalized_text
        if not raw_text and chapters:
            raw_text = "；".join(norm(x) for x in chapters if norm(x))
        status = norm(value.get("status"))
        if not status:
            status = "explicit" if raw_text else "missing"
        semantic_type = norm(value.get("semantic_type")) or (
            infer_semantic_type_from_text(raw_text or normalized_text) if status != "missing" else "unknown"
        )
        final_text = normalized_text or normalize_scope_text(raw_text)
        return build_scope_node(
            status=status,
            semantic_type=semantic_type,
            raw_text=raw_text,
            normalized_text=final_text,
            chapters=[norm(x) for x in chapters if norm(x)] or split_scope_chapters(final_text or raw_text),
            confidence=value.get("confidence"),
            evidence=value.get("evidence") or [],
        )

    text = norm(value)
    if not text:
        return build_scope_node()
    normalized = normalize_scope_text(text)
    semantic_type = infer_semantic_type_from_text(normalized) or default_semantic_type
    return build_scope_node(
        status="explicit",
        semantic_type=semantic_type,
        raw_text=text,
        normalized_text=normalized,
        chapters=split_scope_chapters(normalized),
        confidence=None,
        evidence=[],
    )


def scope_text(node: dict) -> str:
    item = coerce_scope_node(node)
    if item.get("status") == "missing":
        return "未注明"
    text = norm(item.get("raw_text")) or norm(item.get("normalized_text"))
    if text:
        return text
    chapters = item.get("chapters") or []
    if chapters:
        return "；".join(norm(x) for x in chapters if norm(x)) or "未注明"
    return "未注明"


def infer_record_schema(data: dict) -> str:
    if norm(data.get("schema_version")):
        return f"v{norm(data.get('schema_version'))}"
    if isinstance(data.get("entries"), list):
        return "v2-like"
    if isinstance(data.get("subjects"), list):
        return "v1-subjects"
    if data.get("exam_scope") is not None:
        return "v1-single"
    return "unknown"


def extract_entries(data: dict) -> list[dict]:
    rows: list[dict] = []

    entries = data.get("entries")
    if isinstance(entries, list) and entries:
        for item in entries:
            rows.append(
                {
                    "grade": norm(item.get("grade")),
                    "grade_code": norm(item.get("grade_code")),
                    "subject": norm(item.get("subject")),
                    "subject_code": norm(item.get("subject_code")),
                    "midterm": coerce_scope_node(item.get("midterm")),
                    "final": coerce_scope_node(item.get("final")),
                    "weekly_plan": item.get("weekly_plan") or [],
                    "notes": item.get("notes") or [],
                }
            )
        return rows

    subjects = data.get("subjects")
    if isinstance(subjects, list) and subjects:
        for item in subjects:
            scope = item.get("exam_scope") or {}
            rows.append(
                {
                    "grade": norm(item.get("grade_level")) or norm(data.get("grade")),
                    "grade_code": "",
                    "subject": norm(item.get("subject_name")) or norm(data.get("subject")),
                    "subject_code": subject_key(item.get("subject_name")),
                    "midterm": coerce_scope_node(scope.get("midterm"), default_semantic_type="exam_scope"),
                    "final": coerce_scope_node(scope.get("final"), default_semantic_type="exam_scope"),
                    "weekly_plan": [],
                    "notes": [],
                }
            )
        return rows

    if norm(data.get("grade")) or norm(data.get("subject")) or data.get("exam_scope") is not None:
        scope = data.get("exam_scope") or {}
        rows.append(
            {
                "grade": norm(data.get("grade")),
                "grade_code": "",
                "subject": norm(data.get("subject")),
                "subject_code": subject_key(data.get("subject")),
                "midterm": coerce_scope_node(scope.get("midterm"), default_semantic_type="exam_scope"),
                "final": coerce_scope_node(scope.get("final"), default_semantic_type="exam_scope"),
                "weekly_plan": data.get("weekly_plan") or [],
                "notes": data.get("notes") or [],
            }
        )

    return rows


def normalized_record_meta(data: dict) -> dict:
    top_grade_scope = norm(data.get("grade_scope")) or infer_grade_scope_from_grade(data.get("grade"))
    return {
        "schema": infer_record_schema(data),
        "city": norm(data.get("city")),
        "academic_year": norm(data.get("academic_year")),
        "semester": normalize_semester(data.get("semester")),
        "semester_label": semester_label(data.get("semester")),
        "grade_scope": normalize_grade_scope(top_grade_scope),
        "grade_scope_label": grade_scope_label(top_grade_scope),
    }


def record_filter_matches(record: dict, *, city: str = "", academic_year: str = "", semester: str = "", grade_scope: str = "") -> bool:
    if city and norm(record.get("city")) != norm(city):
        return False
    if academic_year and norm(record.get("academic_year")) != norm(academic_year):
        return False
    if semester and normalize_semester(record.get("semester")) != normalize_semester(semester):
        return False
    if grade_scope and normalize_grade_scope(record.get("grade_scope")) != normalize_grade_scope(grade_scope):
        return False
    return True


def record_sort_key(record: dict):
    status = norm(record.get("status"))
    status_score_map = {
        "active": 3,
        "draft": 2,
        "archived": 1,
    }
    status_score = status_score_map.get(status, 0)
    canonical_score = 0
    if norm(record.get("semester")) in {"S1", "S2"}:
        canonical_score += 1
    if norm(record.get("grade_scope")) in {"primary", "junior", "highschool"}:
        canonical_score += 1
    ts = norm(record.get("updated_at")) or norm(record.get("created_at"))
    return (status_score, canonical_score, ts)
