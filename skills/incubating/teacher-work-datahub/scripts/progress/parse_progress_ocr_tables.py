#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
from pathlib import Path

SUBJECTS = ["语文", "数学", "英语", "政治", "历史", "物理", "化学", "生物学", "生物", "地理", "信息技术", "通用技术"]
GRADES = ["高一", "高二", "高三", "初一", "初二", "初三"]
SUBJECT_SET = set(SUBJECTS)
GRADE_SET = set(GRADES)


def norm(v: str) -> str:
    return (v or "").strip()


def normalize_subject(s: str) -> str:
    x = norm(s)
    if x == "生物":
        return "生物学"
    return x


def extract_rows_from_text(text: str) -> list[list[str]]:
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", text, flags=re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)
        parsed = [norm(re.sub(r"<.*?>", "", c, flags=re.S)) for c in cells]
        parsed = [c for c in parsed if c != ""] + [c for c in parsed if c == ""]
        if parsed:
            rows.append(parsed)
    return rows


def parse_row(raw_cells: list[str], current_subject: str) -> tuple[str, str, str, str, str]:
    cells = [norm(c) for c in raw_cells if norm(c)]
    if not cells:
        return current_subject, "", "", "", current_subject

    subject = current_subject
    grade = ""
    midterm = ""
    final = ""

    first = cells[0]
    if first in SUBJECT_SET:
        subject = normalize_subject(first)
        cells = cells[1:]

    # 处理 OCR 头行
    if subject in {"", "科目"} and cells and cells[0] in {"科目", "年级", "期中", "期末"}:
        return current_subject, "", "", "", current_subject

    # 有些行首直接是年级
    if cells and cells[0] in GRADE_SET:
        grade = cells[0]
        cells = cells[1:]

    if not grade:
        for i, c in enumerate(cells):
            if c in GRADE_SET:
                grade = c
                cells = cells[i + 1 :]
                break

    if cells:
        midterm = cells[0]
    if len(cells) >= 2:
        final = cells[1]

    return subject, grade, midterm, final, subject


def build_entries(rows: list[list[str]]) -> list[dict]:
    entries = []
    seen = set()
    current_subject = ""

    for row in rows:
        subject, grade, midterm, final, current_subject = parse_row(row, current_subject)
        subject = normalize_subject(subject)
        grade = norm(grade)
        if subject not in SUBJECT_SET or grade not in GRADE_SET:
            continue
        key = (grade, subject)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "grade": grade,
                "grade_code": "",
                "subject": subject,
                "subject_code": "",
                "midterm": midterm,
                "final": final,
            }
        )
    return entries


def infer_semester(text: str, fallback: str) -> str:
    t = norm(text)
    if "第一学期" in t:
        return "S1"
    if "第二学期" in t:
        return "S2"
    if "S1" in t:
        return "S1"
    if "S2" in t:
        return "S2"
    return fallback


def infer_city(text: str, fallback: str) -> str:
    m = re.search(r"([\u4e00-\u9fa5]{2,10}市)", text)
    if m:
        return m.group(1)
    return fallback


def infer_academic_year(text: str, fallback: str) -> str:
    m = re.search(r"(20\d{2})\D+(20\d{2})\s*学年度", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"(20\d{2})\D*(20\d{2})", text)
    if m:
        y1, y2 = m.group(1), m.group(2)
        if int(y2) == int(y1) + 1:
            return f"{y1}-{y2}"
    return fallback


def load_texts(ocr_files: list[Path]) -> list[str]:
    out = []
    for path in ocr_files:
        if not path.exists():
            continue
        out.append(path.read_text(encoding="utf-8", errors="ignore"))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ocr-file", action="append", default=[])
    parser.add_argument("--ocr-dir", default="")
    parser.add_argument("--city", default="")
    parser.add_argument("--academic-year", default="")
    parser.add_argument("--semester", default="")
    parser.add_argument("--grade-scope", default="highschool")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    ocr_files = [Path(p) for p in args.ocr_file]
    if args.ocr_dir:
        d = Path(args.ocr_dir)
        if d.exists():
            ocr_files.extend(sorted(d.glob("*.txt")))

    texts = load_texts(ocr_files)
    all_rows = []
    for t in texts:
        all_rows.extend(extract_rows_from_text(t))

    entries = build_entries(all_rows)
    merged_text = "\n".join(texts)

    city = infer_city(merged_text, args.city)
    academic_year = infer_academic_year(merged_text, args.academic_year)
    semester = infer_semester(merged_text, args.semester or "S2")

    payload = {
        "city": city,
        "academic_year": academic_year,
        "semester": semester,
        "grade_scope": args.grade_scope or "highschool",
        "doc_type": "teaching_progress_total_table",
        "notes": [
            "由 OCR 表格片段规则解析生成，建议人工抽检关键学科。"
        ],
        "warnings": [
            "若有科目缺失，请补充更多 OCR 片段后重跑。"
        ],
        "entries": entries,
        "stats": {
            "ocr_files": len(ocr_files),
            "rows": len(all_rows),
            "entries": len(entries),
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
