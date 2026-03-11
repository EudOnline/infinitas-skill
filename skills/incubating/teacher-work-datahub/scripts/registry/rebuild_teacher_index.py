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

from catalog_utils import datahub_root, read_json, resolve_workspace_path, write_json  # noqa: E402


def active_sources_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "active_sources.json"


def teacher_index_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "teacher_index.json"


def normalize_class_name(value: str) -> str:
    text = (value or "").strip().replace(" ", "")
    if not text:
        return ""
    if text.endswith("班"):
        return text
    return f"{text}班"


def normalize_subject_name(value: str) -> str:
    return (value or "").strip().replace(" ", "")


def normalize_teacher_name(value: str) -> str:
    return (value or "").strip().replace("\u3000", "").replace(" ", "")


def split_joint_teachers(teacher_raw: str) -> list[str]:
    teacher_raw = normalize_teacher_name(teacher_raw)
    if not teacher_raw:
        return []
    parts = re.split(r"[、,，/]+", teacher_raw)
    return [p for p in (x.strip() for x in parts) if p]


def unwrap_content(obj: dict) -> dict:
    return obj.get("content", obj)


def iter_teacher_rows(data: dict):
    body = unwrap_content(data)
    idx = body.get("teacher_index") or body.get("focus_grade_teacher_index") or {}
    if isinstance(idx, dict) and idx:
        for teacher_raw, rows in idx.items():
            for row in rows or []:
                yield teacher_raw, row
        return

    # 兼容旧版教师配备 structured 结构：从 sheets/sections/subjects 深扫
    sheets = body.get("sheets") or {}
    for sname, sobj in sheets.items():
        for section in sobj.get("sections", []) or []:
            for subject, class_map in (section.get("subjects") or {}).items():
                for cls, teacher_raw in (class_map or {}).items():
                    yield teacher_raw, {
                        "class": cls,
                        "subject": subject,
                        "sheet": sname,
                    }


def infer_grade_from_class_name(class_name: str) -> str:
    raw = (class_name or "").replace("班", "")
    if raw.startswith("25"):
        return "高三"
    if raw.startswith("24"):
        return "高二"
    if raw.startswith("23"):
        return "高一"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--semester", default="S2")
    ap.add_argument("--active-sources-json", default=str(active_sources_path()))
    ap.add_argument("--out", default=str(teacher_index_path()))
    args = ap.parse_args()

    active_sources = read_json(Path(args.active_sources_json), default={}) or {}
    semester_bucket = ((active_sources.get("by_semester") or {}).get(args.semester) or {})
    teacher_source = semester_bucket.get("teacher_allocation")

    if not teacher_source:
        raise SystemExit(f"未找到学期 {args.semester} 的 active teacher_allocation")

    curated_path = teacher_source.get("curated_path")
    if not curated_path:
        raise SystemExit("active teacher_allocation 缺少 curated_path")

    curated_file = resolve_workspace_path(curated_path)
    data = read_json(curated_file, default={}) or {}
    body = unwrap_content(data)

    result = {
        "schema_version": "teacher-work-datahub.teacher-index.v1",
        "teachers": {},
    }

    academic_year = (
        (data.get("record_meta") or {}).get("academic_year")
        or teacher_source.get("academic_year")
        or ""
    )
    semester = args.semester
    focus_grade = body.get("focus_grade") or ""

    for teacher_raw, row in iter_teacher_rows(data):
        subject = normalize_subject_name(row.get("subject", ""))
        class_name = normalize_class_name(row.get("class", ""))
        sheet = row.get("sheet", "")
        teacher_names = split_joint_teachers(teacher_raw)

        for teacher_name in teacher_names:
            bucket = result["teachers"].setdefault(
                teacher_name,
                {
                    "academic_year": academic_year,
                    "semester": semester,
                    "subjects": [],
                    "classes": [],
                    "grades": [],
                    "active_source": {
                        "record_id": teacher_source.get("record_id"),
                        "kind": teacher_source.get("kind"),
                    },
                    "evidence": [],
                },
            )

            if subject and subject not in bucket["subjects"]:
                bucket["subjects"].append(subject)
            if class_name and class_name not in bucket["classes"]:
                bucket["classes"].append(class_name)
            inferred_grade = infer_grade_from_class_name(class_name)
            if focus_grade and focus_grade not in {"高", "年级"} and len(focus_grade) >= 2 and focus_grade not in bucket["grades"]:
                bucket["grades"].append(focus_grade)
            elif inferred_grade and inferred_grade not in bucket["grades"]:
                bucket["grades"].append(inferred_grade)

            bucket["evidence"].append(
                {
                    "teacher_raw": teacher_raw,
                    "sheet": sheet,
                    "subject": subject,
                    "class": row.get("class", ""),
                }
            )

    for teacher_name, info in result["teachers"].items():
        info["subjects"] = sorted(info["subjects"])
        info["classes"] = sorted(info["classes"])
        info["grades"] = sorted(info["grades"])

    write_json(Path(args.out), result)
    print(
        json.dumps(
            {
                "success": True,
                "teacher_count": len(result["teachers"]),
                "output_path": args.out,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
