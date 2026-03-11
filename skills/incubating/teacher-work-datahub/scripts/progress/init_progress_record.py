#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
DATAHUB_ROOT = WORKSPACE_ROOT / "data/teacher-work-datahub"


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

GRADE_SCOPE_MAP = {
    "primary": "primary",
    "小学": "primary",
    "junior": "junior",
    "初中": "junior",
    "highschool": "highschool",
    "高中": "highschool",
}

GRADE_CODE_MAP = {
    "高一": "g1",
    "高二": "g2",
    "高三": "g3",
    "初一": "j1",
    "初二": "j2",
    "初三": "j3",
}

SUBJECT_CODE_MAP = {
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


def norm(value: str) -> str:
    return (value or "").strip()


def normalize_semester(value: str) -> str:
    v = norm(value)
    return SEMESTER_MAP.get(v, v)


def normalize_grade_scope(value: str) -> str:
    v = norm(value)
    if v in GRADE_SCOPE_MAP:
        return GRADE_SCOPE_MAP[v]
    if v in {"高一", "高二", "高三"}:
        return "highschool"
    if v in {"初一", "初二", "初三"}:
        return "junior"
    return v


def infer_grade_scope_from_grade(grade: str) -> str:
    g = norm(grade)
    if g in {"高一", "高二", "高三"}:
        return "highschool"
    if g in {"初一", "初二", "初三"}:
        return "junior"
    return ""


def grade_code_for(grade: str) -> str:
    return GRADE_CODE_MAP.get(norm(grade), "")


def subject_code_for(subject: str) -> str:
    return SUBJECT_CODE_MAP.get(norm(subject), "")


def build_key(city: str, academic_year: str, semester: str, grade_scope: str) -> str:
    return f"{norm(city)}::{norm(academic_year)}::{norm(semester)}::{norm(grade_scope)}"


def empty_scope_node() -> dict:
    return {
        "status": "missing",
        "semantic_type": "unknown",
        "raw_text": "",
        "normalized_text": "",
        "chapters": [],
        "confidence": None,
        "evidence": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", required=True)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--semester", required=True)
    parser.add_argument("--grade-scope", default="")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--doc-type", default="teaching_progress_total_table")
    parser.add_argument("--version", default="")
    parser.add_argument("--status", default="draft")
    parser.add_argument("--record-id", default="")
    parser.add_argument("--out", required=True)

    # Backward-compatible optional single-entry bootstrap
    parser.add_argument("--grade", default="")
    parser.add_argument("--subject", default="")
    args = parser.parse_args()

    if bool(norm(args.grade)) != bool(norm(args.subject)):
        parser.error("--grade and --subject must be provided together when creating an initial entry")

    source = Path(args.source_file)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    semester = normalize_semester(args.semester)
    grade_scope = normalize_grade_scope(args.grade_scope) or infer_grade_scope_from_grade(args.grade)
    if not grade_scope:
        parser.error("--grade-scope is required unless it can be inferred from --grade")

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    record = {
        "schema_version": "2.0",
        "doc_type": norm(args.doc_type) or "teaching_progress_total_table",
        "city": norm(args.city),
        "academic_year": norm(args.academic_year),
        "semester": semester,
        "grade_scope": grade_scope,
        "source": {
            "file": str(source),
            "filename": source.name,
            "status": norm(args.status) or "draft",
            "version": norm(args.version) or datetime.now().strftime("%Y-%m-%d"),
            "updated_at": now,
        },
        "catalog": {
            "record_id": norm(args.record_id),
            "key": build_key(args.city, args.academic_year, semester, grade_scope),
        },
        "entries": [],
        "warnings": [],
        "notes": [],
        "stats": {
            "entry_count": 0,
        },
    }

    if norm(args.grade) and norm(args.subject):
        record["entries"].append(
            {
                "grade": norm(args.grade),
                "grade_code": grade_code_for(args.grade),
                "subject": norm(args.subject),
                "subject_code": subject_code_for(args.subject),
                "midterm": empty_scope_node(),
                "final": empty_scope_node(),
                "weekly_plan": [],
                "notes": [],
            }
        )
        record["stats"]["entry_count"] = len(record["entries"])

    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
