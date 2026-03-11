#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
from pathlib import Path

GRADE_SCOPE_MAP = {
    "高中": "highschool",
    "初中": "junior",
    "小学": "primary",
}

SEMESTER_MAP = {
    "第一学期": "S1",
    "第二学期": "S2",
}

VALID_GRADES = {"高一", "高二", "高三", "初一", "初二", "初三"}


def norm(value: str) -> str:
    return (value or "").strip()


def normalize_subject(subject: str) -> str:
    s = norm(subject)
    if s == "生物":
        return "生物学"
    return s


def clean_cell(text: str) -> str:
    t = norm(text)
    t = t.replace("<br>", "；").replace("<br/>", "；").replace("<br />", "；")
    t = re.sub(r"\s+", " ", t)
    t = t.replace("Unit 6第四册", "Unit 6 第四册")
    t = t.replace("1、", "1、")
    t = t.replace("2、", "2、")
    return t.strip()


def extract_title(text: str) -> str:
    for line in text.splitlines():
        line = norm(line)
        if not line or line.startswith("|"):
            continue
        if "教学进度表" in line or "考试范围" in line or "教学安排" in line:
            return line
    return ""


def parse_title_meta(title: str) -> dict:
    title = norm(title)
    city = ""
    academic_year = ""
    semester = ""
    grade_scope = ""

    m_city = re.search(r"([\u4e00-\u9fa5]{2,10}市)", title)
    if m_city:
        city = m_city.group(1)

    m_year = re.search(r"(20\d{2})\s*[—-]\s*(20\d{2})", title)
    if m_year:
        academic_year = f"{m_year.group(1)}-{m_year.group(2)}"

    for k, v in SEMESTER_MAP.items():
        if k in title:
            semester = v
            break

    for k, v in GRADE_SCOPE_MAP.items():
        if k in title:
            grade_scope = v
            break

    return {
        "title": title,
        "city": city,
        "academic_year": academic_year,
        "semester": semester,
        "grade_scope": grade_scope,
    }


def split_markdown_row(line: str) -> list[str]:
    raw = line.strip()
    if not raw.startswith("|"):
        return []
    parts = [clean_cell(x) for x in raw.strip("|").split("|")]
    return parts


def is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    joined = "".join(cells).replace("-", "").replace(":", "").strip()
    return joined == ""


def parse_markdown_table_text(text: str) -> dict:
    title = extract_title(text)
    meta = parse_title_meta(title)

    entries = []
    warnings = []
    last_subject = ""

    table_lines = [line for line in text.splitlines() if line.strip().startswith("|")]
    for idx, line in enumerate(table_lines, start=1):
        cells = split_markdown_row(line)
        if not cells or is_separator_row(cells):
            continue
        if cells[:4] == ["科目", "年级", "期中", "期末"]:
            continue

        while len(cells) < 4:
            cells.append("")
        if len(cells) > 4:
            cells = cells[:4]

        subject, grade, midterm, final = cells
        subject = normalize_subject(subject)
        grade = norm(grade)

        if grade not in VALID_GRADES and subject in VALID_GRADES:
            subject, grade, midterm, final = "", subject, grade, midterm
            grade = norm(grade)

        if grade not in VALID_GRADES:
            continue

        if subject:
            last_subject = subject
        else:
            subject = last_subject

        if not subject:
            warnings.append(f"row_{idx}: missing subject for grade={grade}")
            continue

        entries.append(
            {
                "grade": grade,
                "subject": subject,
                "midterm": clean_cell(midterm),
                "final": clean_cell(final),
            }
        )

    doc_type = "teaching_progress_subject_table" if len({e['subject'] for e in entries}) <= 1 else "teaching_progress_total_table"
    return {
        "doc_type": doc_type,
        "title": meta["title"],
        "city": meta["city"],
        "academic_year": meta["academic_year"],
        "semester": meta["semester"],
        "grade_scope": meta["grade_scope"],
        "entries": entries,
        "notes": [],
        "warnings": warnings,
        "stats": {
            "entry_count": len(entries),
            "subject_count": len({e['subject'] for e in entries}),
            "grade_count": len({e['grade'] for e in entries}),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="input_path", required=True)
    parser.add_argument("--out", dest="output_path", default="")
    args = parser.parse_args()

    src = Path(args.input_path)
    text = src.read_text(encoding="utf-8")
    payload = parse_markdown_table_text(text)

    if args.output_path:
        out = Path(args.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(out)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
