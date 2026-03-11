#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
先反合并再解析“教师配备一览表”(.xls)
输出 datahub envelope：record_meta + content
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import xlrd


def norm_cell(v) -> str:
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return str(v)
    return str(v).strip()


def normalize_label(s: str) -> str:
    return s.replace(" ", "").replace("\u3000", "").strip()


def clean_teacher_name(name: str) -> str:
    s = normalize_label(name)
    s = s.replace("—", "").replace("→", "")
    s = s.replace("-", "")
    return s


def is_class_code(s: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", normalize_label(s)))


def grade_match(grade_label: str, focus_grade: str) -> bool:
    return normalize_label(focus_grade) in normalize_label(grade_label)


def unmerge_fill(rows: List[List[str]], merged_cells: List[Tuple[int, int, int, int]]) -> List[List[str]]:
    filled = [row[:] for row in rows]
    for rlo, rhi, clo, chi in merged_cells:
        top = rows[rlo][clo]
        for r in range(rlo, rhi):
            for c in range(clo, chi):
                if not filled[r][c]:
                    filled[r][c] = top
    return filled


def parse_sheet(sheet: xlrd.sheet.Sheet, preview_merged: int = 20) -> Dict:
    rows = [[norm_cell(sheet.cell_value(r, c)) for c in range(sheet.ncols)] for r in range(sheet.nrows)]

    merged_preview = []
    for rlo, rhi, clo, chi in sheet.merged_cells[:preview_merged]:
        merged_preview.append(
            {
                "rlo": rlo,
                "rhi": rhi,
                "clo": clo,
                "chi": chi,
                "top_left": rows[rlo][clo],
            }
        )

    filled = unmerge_fill(rows, sheet.merged_cells)
    starts = [i for i, row in enumerate(filled) if row and normalize_label(row[0]) == "年级"]
    boundaries = starts + [sheet.nrows]

    sections = []
    for si, st in enumerate(starts):
        ed = boundaries[si + 1]

        class_idx = None
        for r in range(st, ed):
            if normalize_label(filled[r][0]) == "班次":
                class_idx = r
                break
        if class_idx is None:
            continue

        grade_row = filled[st]
        class_row = filled[class_idx]

        class_cols = []
        for c, v in enumerate(class_row):
            if is_class_code(v):
                class_cols.append((c, normalize_label(v)))

        section = {
            "row_range_1based": [st + 1, ed],
            "grade_header_row_1based": st + 1,
            "class_row_1based": class_idx + 1,
            "classes": [
                {"col": c, "class": cls, "grade": grade_row[c] if c < len(grade_row) else ""}
                for c, cls in class_cols
            ],
            "subjects": {},
        }

        for r in range(class_idx + 1, ed):
            subj_raw = filled[r][0]
            subj = normalize_label(subj_raw)
            if not subj or subj in ("年级", "班次"):
                continue

            values = {}
            for c, cls in class_cols:
                val = filled[r][c].strip() if c < len(filled[r]) else ""
                if val:
                    values[cls] = val
            if values:
                section["subjects"][subj] = values

        sections.append(section)

    return {
        "rows": sheet.nrows,
        "cols": sheet.ncols,
        "merged_count": len(sheet.merged_cells),
        "merged_preview": merged_preview,
        "sections": sections,
    }


def build_focus(root: Dict, focus_grade: str) -> Tuple[List[str], Dict[str, Dict[str, str]], Dict[str, List[Dict]]]:
    focus_classes = []
    by_class: Dict[str, Dict[str, str]] = {}
    teacher_index: Dict[str, List[Dict]] = {}

    for sname, sobj in root["sheets"].items():
        for section in sobj.get("sections", []):
            section_classes = [
                x["class"] for x in section.get("classes", []) if grade_match(x.get("grade", ""), focus_grade)
            ]
            if not section_classes:
                continue

            for cls in section_classes:
                focus_classes.append(cls)
                by_class.setdefault(cls, {})
                for subj, class_map in section.get("subjects", {}).items():
                    if cls in class_map:
                        teacher_raw = class_map[cls]
                        by_class[cls][subj] = teacher_raw

                        clean = clean_teacher_name(teacher_raw)
                        teacher_index.setdefault(clean, []).append(
                            {
                                "teacher_raw": teacher_raw,
                                "class": cls,
                                "subject": subj,
                                "sheet": sname,
                            }
                        )

    focus_classes = sorted(set(focus_classes))
    return focus_classes, by_class, teacher_index


def main():
    parser = argparse.ArgumentParser(description="反合并后解析教师配备表(.xls)")
    parser.add_argument("--input", required=True, help="输入 .xls 文件路径")
    parser.add_argument("--output", required=True, help="输出 JSON 路径")
    parser.add_argument("--focus-grade", default="高二", help="聚焦年级（默认: 高二）")
    parser.add_argument("--teacher", default="", help="可选：指定教师名做查询")
    parser.add_argument("--preview-merged", type=int, default=20, help="输出合并预览数量")
    parser.add_argument("--academic-year", default="2025-2026", help="学年")
    parser.add_argument("--semester", default="S2", help="学期代码")
    parser.add_argument("--source-name", default="", help="来源名（默认取文件名）")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {in_path}")

    wb = xlrd.open_workbook(str(in_path), formatting_info=True)

    content = {
        "source_file": str(in_path),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "parse_mode": "unmerge_then_parse",
        "sheet_count": wb.nsheets,
        "focus_grade": args.focus_grade,
        "sheets": {},
    }

    for sname in wb.sheet_names():
        content["sheets"][sname] = parse_sheet(wb.sheet_by_name(sname), preview_merged=args.preview_merged)

    focus_classes, by_class, teacher_index = build_focus(content, args.focus_grade)
    content["focus_grade_classes"] = focus_classes
    content["focus_grade_subjects_by_class"] = by_class
    content["focus_grade_teacher_index"] = teacher_index

    if args.teacher:
        tq = clean_teacher_name(args.teacher)
        content["teacher_query"] = {
            "raw": args.teacher,
            "clean": tq,
            "matches": teacher_index.get(tq, []),
        }

    result = {
        "schema_version": "teacher-work-datahub.teacher-allocation.v1",
        "record_meta": {
            "source_name": args.source_name or in_path.name,
            "source_file": str(in_path),
            "academic_year": args.academic_year,
            "semester": args.semester,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "parser": "parse_teacher_allocation.py",
        },
        "content": content,
    }

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 输出: {out_path}")
    for sname, sobj in content["sheets"].items():
        print(f"[INFO] {sname}: merged_count={sobj.get('merged_count', 0)}")
    if focus_classes:
        print(f"[INFO] {args.focus_grade}班级: {', '.join(focus_classes)}")
    if args.teacher:
        matches = content.get("teacher_query", {}).get("matches", [])
        print(f"[INFO] 教师查询({args.teacher}) 命中: {len(matches)}")
        for item in matches:
            print(f"  - {item['class']} {item['subject']} ({item['sheet']})")


if __name__ == "__main__":
    main()
