#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from catalog_utils import datahub_root, read_json  # noqa: E402


def teacher_index_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "teacher_index.json"


def normalize_teacher_name(value: str) -> str:
    return (value or "").strip().replace(" ", "").replace("\u3000", "")


def find_teacher(teachers: dict, teacher_name: str):
    if teacher_name in teachers:
        return teacher_name, teachers[teacher_name]

    target = normalize_teacher_name(teacher_name)
    for name, info in teachers.items():
        if normalize_teacher_name(name) == target:
            return name, info

    return None, None


def format_text(name: str, info: dict) -> str:
    academic_year = info.get("academic_year", "")
    semester = info.get("semester", "")
    classes = info.get("classes") or []
    subjects = info.get("subjects") or []
    grades = info.get("grades") or []
    source = info.get("active_source") or {}

    classes_text = "、".join(classes) if classes else "未标出班级"
    subjects_text = "、".join(subjects) if subjects else "未标出学科"
    grades_text = "、".join(grades) if grades else "未标出年级"

    lines = [
        f"{name}（{academic_year} / {semester}）当前 active 任教班级：{classes_text}；学科：{subjects_text}；年级：{grades_text}。",
        f"数据来源：{source.get('kind', '')} / {source.get('record_id', '')}",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--teacher-index-json", default=str(teacher_index_path()))
    args = ap.parse_args()

    index_data = read_json(Path(args.teacher_index_json), default={}) or {}
    teachers = index_data.get("teachers") or {}

    name, info = find_teacher(teachers, args.teacher)
    if not info:
        msg = f"当前 active 教师配备数据中未找到“{args.teacher}”。如需查询历史版本，请显式指定版本或学期。"
        if args.format == "json":
            print(json.dumps({"success": False, "error": msg}, ensure_ascii=False, indent=2))
        else:
            print(msg)
        return

    if args.format == "json":
        print(json.dumps({"success": True, "teacher": name, "data": info}, ensure_ascii=False, indent=2))
    else:
        print(format_text(name, info))


if __name__ == "__main__":
    main()
