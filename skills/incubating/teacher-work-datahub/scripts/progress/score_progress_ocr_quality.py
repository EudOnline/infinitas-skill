#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

from parse_progress_markdown_table import extract_title, parse_markdown_table_text

EXPECTED_SUBJECTS_HIGHSCHOOL = {"语文", "数学", "英语", "政治", "历史", "物理", "化学", "生物学", "地理", "信息技术", "通用技术"}
EXPECTED_GRADES_HIGHSCHOOL = {"高一", "高二", "高三"}


def norm(v: str) -> str:
    return (v or "").strip()


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--grade-scope", default="highschool")
    args = parser.parse_args()

    src = Path(args.markdown)
    text = load_text(src)
    parsed = parse_markdown_table_text(text)

    title = extract_title(text)
    entries = parsed.get("entries") or []
    stats = parsed.get("stats") or {}
    subjects = {norm(item.get("subject")) for item in entries if norm(item.get("subject"))}
    grades = {norm(item.get("grade")) for item in entries if norm(item.get("grade"))}

    score = 0
    issues = []
    suggestions = []

    if title:
        score += 15
    else:
        issues.append("missing_title")
        suggestions.append("检查 OCR 输出是否保留标题行")

    if "| 科目 | 年级 | 期中 | 期末 |" in text:
        score += 15
    else:
        issues.append("missing_header_row")
        suggestions.append("检查模型是否输出 Markdown 表头")

    entry_count = stats.get("entry_count", 0)
    if entry_count >= 25:
        score += 20
    elif entry_count >= 15:
        score += 10
        issues.append("low_entry_count")
    else:
        issues.append("very_low_entry_count")
        suggestions.append("切换后备模型或补充人工复核")

    subject_count = stats.get("subject_count", 0)
    if args.grade_scope == "highschool":
        missing_subjects = sorted(EXPECTED_SUBJECTS_HIGHSCHOOL - subjects)
        if subject_count >= 10:
            score += 20
        elif subject_count >= 8:
            score += 10
            issues.append("subject_count_below_expected")
        else:
            issues.append("subject_count_too_low")
            suggestions.append("优先切换 Qwen 后备模型")
        if missing_subjects:
            issues.append(f"missing_subjects:{','.join(missing_subjects)}")

        missing_grades = sorted(EXPECTED_GRADES_HIGHSCHOOL - grades)
        if len(grades) == 3:
            score += 15
        elif len(grades) == 2:
            score += 8
            issues.append("grade_coverage_incomplete")
        else:
            issues.append("grade_coverage_too_low")
            suggestions.append("检查表格解析是否丢失整段年级")
        if missing_grades:
            issues.append(f"missing_grades:{','.join(missing_grades)}")
    else:
        score += 20 if subject_count > 0 else 0
        score += 15 if len(grades) > 0 else 0

    bad_markers = 0
    for marker in ["}}", "<|box_start|>", "<|md_start|>"]:
        if marker in text:
            bad_markers += 1
    if bad_markers == 0:
        score += 15
    else:
        issues.append(f"bad_markers:{bad_markers}")
        suggestions.append("当前 OCR 输出含残缺标记，建议切换模型或清洗原文")

    risk_level = "low"
    if score < 60:
        risk_level = "high"
    elif score < 80:
        risk_level = "medium"

    result = {
        "score": score,
        "risk_level": risk_level,
        "title": title,
        "entry_count": entry_count,
        "subject_count": subject_count,
        "grade_count": stats.get("grade_count", 0),
        "issues": issues,
        "suggestions": suggestions,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
