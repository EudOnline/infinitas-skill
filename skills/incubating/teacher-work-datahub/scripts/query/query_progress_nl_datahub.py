#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from catalog_utils import datahub_root, read_json, resolve_workspace_path  # noqa: E402
from progress_query_utils import (  # noqa: E402
    build_review_notice,
    extract_entries,
    grade_matches,
    infer_grade_scope_from_grade,
    normalize_grade_scope,
    normalize_semester,
    record_sort_key,
    scope_text,
    semantic_type_label,
    semester_label,
    subject_matches,
)

SUBJECTS = ["语文", "数学", "英语", "政治", "历史", "物理", "化学", "生物", "生物学", "地理", "信息技术", "通用技术"]
GRADES = ["高一", "高二", "高三", "高中", "初一", "初二", "初三", "初中"]
SEMESTERS = ["第一学期", "第二学期", "上学期", "下学期", "S1", "S2"]


def catalog_json_path() -> Path:
    return datahub_root() / "catalog" / "sources.json"


def semester_context_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "semester_context.json"


def norm(v: str) -> str:
    return (v or "").strip()


def parse_request(text: str) -> dict:
    t = norm(text)
    grade = next((g for g in GRADES if g in t), "")
    subject = next((s for s in SUBJECTS if s in t), "")
    exam = "both"
    if "期中" in t:
        exam = "midterm"
    elif "期末" in t:
        exam = "final"
    semester = next((s for s in SEMESTERS if s in t), "")
    city = ""
    m = re.search(r"([\u4e00-\u9fa5]{2,10}市)", t)
    if m:
        city = m.group(1)
    return {
        "text": t,
        "city": city,
        "semester": semester,
        "grade": grade,
        "subject": subject,
        "exam": exam,
    }


def choose_best_record(records: list[dict]) -> dict | None:
    if not records:
        return None
    return sorted(records, key=record_sort_key, reverse=True)[0]


def record_filter_matches(record: dict, *, city: str = "", academic_year: str = "", semester: str = "", grade_scope: str = "") -> bool:
    if record.get("domain") != "teaching_progress":
        return False
    metadata = record.get("metadata") or {}
    if city and norm(metadata.get("city")) != norm(city):
        return False
    if academic_year and norm(record.get("academic_year")) != norm(academic_year):
        return False
    if semester and normalize_semester(record.get("semester")) != normalize_semester(semester):
        return False
    if grade_scope and normalize_grade_scope(metadata.get("grade_scope")) != normalize_grade_scope(grade_scope):
        return False
    return True


def build_human_answer(result: dict) -> str:
    resolved = result.get("resolved") or {}
    review_notice = result.get("review_notice") or {}
    rows = result.get("rows") or []
    parsed = result.get("request_parse") or {}

    city = norm(resolved.get("city")) or "未指定地市"
    academic_year = norm(resolved.get("academic_year")) or "未指定学年"
    semester = semester_label(resolved.get("semester")) or norm(resolved.get("semester")) or "未指定学期"
    grade = norm(parsed.get("grade")) or "未指定年级"
    subject = norm(parsed.get("subject"))
    exam = norm(parsed.get("exam"))
    exam_label = {"midterm": "期中", "final": "期末", "both": "期中/期末"}.get(exam, exam or "考试")

    lines = []
    if review_notice.get("needs_review") and review_notice.get("message"):
        lines.append(f"【提示】{review_notice.get('message')}")
        lines.append("")

    if not rows:
        target = f"{grade}{subject or ''}{exam_label}"
        lines.append(f"未查到 {city} {academic_year} {semester} {target} 的结构化结果。")
        return "\n".join(lines).strip()

    if subject:
        lines.append(f"{city} {academic_year} {semester}{grade}{subject}{exam_label}范围：")
        lines.append("")
        row = rows[0]
        node = row.get("midterm") if exam == "midterm" else row.get("final") if exam == "final" else None
        if node:
            lines.append(f"- {node.get('text', '未注明')}")
            if node.get("semantic_type_label") and node.get("semantic_type") != "exam_scope":
                lines.append(f"- 说明：{node.get('semantic_type_label')}")
    else:
        lines.append(f"{city} {academic_year} {semester}{grade}{exam_label}范围如下：")
        lines.append("")
        for row in rows:
            node = row.get("midterm") if exam == "midterm" else row.get("final") if exam == "final" else None
            if node is None and exam == "both":
                continue
            lines.append(f"- {row.get('subject', '未命名学科')}：{(node or {}).get('text', '未注明')}")
            if (node or {}).get("semantic_type") not in {"", "exam_scope", None}:
                lines.append(f"  （{(node or {}).get('semantic_type_label', '')}）")

    return "\n".join(lines).strip()


def run_query(*, catalog_path: Path, context_path: Path, text: str) -> dict:
    parsed = parse_request(text)
    context_defaults = read_json(context_path, default={}) or {}
    current = context_defaults.get("current") or {}
    city = parsed["city"] or current.get("city", "")
    semester = normalize_semester(parsed["semester"] or current.get("semester", ""))
    academic_year = current.get("academic_year", "")
    inferred_grade_scope = normalize_grade_scope(infer_grade_scope_from_grade(parsed["grade"]))
    grade_scope = inferred_grade_scope or normalize_grade_scope(current.get("grade_scope", ""))

    catalog = read_json(catalog_path, default={}) or {}
    candidates = []
    for record in catalog.get("records") or []:
        if not record_filter_matches(
            record,
            city=city,
            academic_year=academic_year,
            semester=semester,
            grade_scope=grade_scope,
        ):
            continue
        candidates.append(record)
    record = choose_best_record(candidates)

    result = {
        "request_parse": parsed,
        "resolved": {
            "city": city,
            "academic_year": academic_year,
            "semester": semester,
            "grade_scope": grade_scope,
            "record_id": record.get("record_id", "") if record else "",
            "record_found": bool(record),
            "candidate_count": len(candidates),
            "record_status": record.get("status", "") if record else "",
        },
        "review_notice": {
            "needs_review": False,
            "status": "",
            "status_label": "",
            "message": "",
            "issues": [],
            "actions": [],
        },
        "rows": [],
    }
    if not record:
        return result

    data = read_json(resolve_workspace_path(record["curated_path"]), default={}) or {}
    result["review_notice"] = build_review_notice(record, data)
    for item in extract_entries(data):
        if not grade_matches(item.get("grade", ""), parsed["grade"]):
            continue
        if not subject_matches(item.get("subject", ""), parsed["subject"]):
            continue
        row = {
            "grade": item.get("grade", ""),
            "subject": item.get("subject", ""),
        }
        if parsed["exam"] in ("midterm", "both"):
            node = item.get("midterm") or {}
            row["midterm"] = {
                "text": scope_text(node),
                "status": node.get("status", "missing"),
                "semantic_type": node.get("semantic_type", "unknown"),
                "semantic_type_label": semantic_type_label(node.get("semantic_type", "unknown")),
                "raw_text": node.get("raw_text", ""),
            }
        if parsed["exam"] in ("final", "both"):
            node = item.get("final") or {}
            row["final"] = {
                "text": scope_text(node),
                "status": node.get("status", "missing"),
                "semantic_type": node.get("semantic_type", "unknown"),
                "semantic_type_label": semantic_type_label(node.get("semantic_type", "unknown")),
                "raw_text": node.get("raw_text", ""),
            }
        result["rows"].append(row)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-json", default=str(catalog_json_path()))
    parser.add_argument("--context-json", default=str(semester_context_path()))
    parser.add_argument("--text", required=True)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    result = run_query(
        catalog_path=Path(args.catalog_json),
        context_path=Path(args.context_json),
        text=args.text,
    )

    if args.format == "text":
        print(build_human_answer(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
