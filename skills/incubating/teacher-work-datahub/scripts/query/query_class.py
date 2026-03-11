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


def class_index_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "class_index.json"


def normalize_class_name(value: str) -> str:
    text = (value or "").strip().replace(" ", "")
    if not text:
        return ""
    if text.endswith("班"):
        return text
    return f"{text}班"


def normalize_subject_name(value: str) -> str:
    return (value or "").strip().replace(" ", "")


def format_text(class_name: str, info: dict, subject: str = "") -> str:
    academic_year = info.get("academic_year", "")
    semester = info.get("semester", "")
    grade = info.get("grade", "")
    subjects = info.get("subjects") or {}
    source = info.get("active_source") or {}

    if subject:
        subject_teachers = subjects.get(subject) or []
        if subject_teachers:
            return (
                f"{class_name}（{academic_year} / {semester} / {grade}）"
                f"{subject}教师：{'、'.join(subject_teachers)}。\n"
                f"数据来源：{source.get('kind', '')} / {source.get('record_id', '')}"
            )
        return (
            f"{class_name}（{academic_year} / {semester} / {grade}）"
            f"当前 active 数据中未找到学科“{subject}”。\n"
            f"数据来源：{source.get('kind', '')} / {source.get('record_id', '')}"
        )

    lines = [f"{class_name}（{academic_year} / {semester} / {grade}）当前任课信息："]
    for subj in sorted(subjects.keys()):
        lines.append(f"- {subj}：{'、'.join(subjects[subj])}")
    lines.append(f"数据来源：{source.get('kind', '')} / {source.get('record_id', '')}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="class_name", required=True)
    ap.add_argument("--subject", default="")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--class-index-json", default=str(class_index_path()))
    args = ap.parse_args()

    class_name = normalize_class_name(args.class_name)
    subject = normalize_subject_name(args.subject)

    index_data = read_json(Path(args.class_index_json), default={}) or {}
    classes = index_data.get("classes") or {}
    info = classes.get(class_name)

    if not info:
        msg = f"当前 active 教师配备数据中未找到班级“{class_name}”。"
        if args.format == "json":
            print(json.dumps({"success": False, "error": msg}, ensure_ascii=False, indent=2))
        else:
            print(msg)
        return

    if args.format == "json":
        out = {"success": True, "class": class_name, "data": info}
        if subject:
            out["subject"] = subject
            out["teachers"] = (info.get("subjects") or {}).get(subject) or []
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(format_text(class_name, info, subject))


if __name__ == "__main__":
    main()
