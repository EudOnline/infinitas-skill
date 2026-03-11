#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from catalog_utils import datahub_root, read_json, resolve_workspace_path  # noqa: E402
from progress_query_utils import extract_entries, load_json, normalized_record_meta, scope_text, semantic_type_label  # noqa: E402

GRADE_ORDER = {
    "高一": 1,
    "高二": 2,
    "高三": 3,
    "初一": 11,
    "初二": 12,
    "初三": 13,
}

SUBJECT_ORDER = {
    "语文": 1,
    "数学": 2,
    "英语": 3,
    "政治": 4,
    "历史": 5,
    "物理": 6,
    "化学": 7,
    "生物": 8,
    "生物学": 8,
    "地理": 9,
    "信息技术": 10,
    "通用技术": 11,
}


def lineage_out_dir() -> Path:
    return datahub_root() / "outputs" / "reports" / "teaching-progress"


def grade_sort_key(item: dict):
    grade = item.get("grade", "")
    subject = item.get("subject", "")
    return (GRADE_ORDER.get(grade, 999), SUBJECT_ORDER.get(subject, 999), grade, subject)


def render_scope_block(label: str, node: dict) -> list[str]:
    return [
        f"- {label}：{scope_text(node)}",
        f"  - 类型：{semantic_type_label(node.get('semantic_type', 'unknown'))}",
        f"  - 状态：{node.get('status', 'missing')}",
    ]


def choose_active_progress_record(catalog: dict, semester: str) -> dict | None:
    active = [r for r in (catalog.get("records") or []) if r.get("domain") == "teaching_progress" and r.get("semester") == semester and r.get("status") == "active"]
    return active[-1] if active else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--semester", default="S2")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    catalog = read_json(datahub_root() / "catalog" / "sources.json", default={}) or {}
    record = choose_active_progress_record(catalog, args.semester)
    if not record:
        raise SystemExit(f"未找到学期 {args.semester} 的 active 教学进度记录")

    data = load_json(resolve_workspace_path(record["curated_path"]))
    meta = normalized_record_meta(data)
    entries = sorted(extract_entries(data), key=grade_sort_key)

    title = f"{meta['city']} {meta['academic_year']} {meta['semester_label']} {meta['grade_scope_label']}教学进度与考试范围摘要"
    lines = [
        f"# {title}",
        "",
        "## 基本信息",
        f"- 地市：{meta['city']}",
        f"- 学年：{meta['academic_year']}",
        f"- 学期：{meta['semester_label']}（{meta['semester']}）",
        f"- 学段：{meta['grade_scope_label']}（{meta['grade_scope']}）",
        f"- 结构版本：{data.get('schema_version', meta['schema'])}",
        f"- record_id：{record.get('record_id', '')}",
        f"- 数据源：{record.get('source_name', '')}",
        "",
    ]

    grouped = {}
    for item in entries:
        grouped.setdefault(item.get("grade", "未分级"), []).append(item)

    for grade in sorted(grouped.keys(), key=lambda g: GRADE_ORDER.get(g, 999)):
        lines.append(f"## {grade}")
        for item in sorted(grouped[grade], key=grade_sort_key):
            lines.append(f"### {item.get('subject', '未命名学科')}")
            lines.extend(render_scope_block("期中", item.get("midterm") or {}))
            lines.extend(render_scope_block("期末", item.get("final") or {}))
            lines.append("")

    out = Path(args.out).expanduser() if args.out else lineage_out_dir() / f"教学进度摘要-{meta['city']}-{meta['academic_year']}-{meta['semester']}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
