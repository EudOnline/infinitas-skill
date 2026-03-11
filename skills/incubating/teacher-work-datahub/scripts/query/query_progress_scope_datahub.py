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

from catalog_utils import datahub_root, read_json, resolve_workspace_path  # noqa: E402
from progress_query_utils import (  # noqa: E402
    extract_entries,
    grade_matches,
    normalized_record_meta,
    scope_text,
    semantic_type_label,
    subject_matches,
)


def catalog_json_path() -> Path:
    return datahub_root() / "catalog" / "sources.json"


def semester_context_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "semester_context.json"


def choose_active_record(records: list[dict], semester: str, kind: str = "teaching_progress_total_table") -> dict | None:
    active = [r for r in records if r.get("kind") == kind and r.get("semester") == semester and r.get("status") == "active"]
    if active:
        return active[-1]
    candidates = [r for r in records if r.get("kind") == kind and r.get("semester") == semester]
    return candidates[-1] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-json", default=str(catalog_json_path()))
    parser.add_argument("--context-json", default=str(semester_context_path()))
    parser.add_argument("--semester", default="")
    parser.add_argument("--grade", default="")
    parser.add_argument("--subject", default="")
    parser.add_argument("--exam", choices=["midterm", "final", "both"], default="both")
    args = parser.parse_args()

    catalog = read_json(Path(args.catalog_json), default={}) or {}
    ctx = read_json(Path(args.context_json), default={}) or {}
    semester = args.semester or ((ctx.get("current") or {}).get("semester") or "S2")

    record = choose_active_record(catalog.get("records") or [], semester=semester)
    if not record:
        print(json.dumps({"success": False, "error": f"未找到学期 {semester} 的教学进度记录"}, ensure_ascii=False, indent=2))
        return 0

    data = read_json(resolve_workspace_path(record.get("curated_path", "")), default={}) or {}
    meta = normalized_record_meta(data)
    entries = extract_entries(data)
    rows = []
    for item in entries:
        if not grade_matches(item.get("grade", ""), args.grade):
            continue
        if not subject_matches(item.get("subject", ""), args.subject):
            continue
        row = {
            "grade": item.get("grade", ""),
            "subject": item.get("subject", ""),
        }
        if args.exam in ("midterm", "both"):
            node = item.get("midterm") or {}
            row["midterm"] = {
                "text": scope_text(node),
                "status": node.get("status", "missing"),
                "semantic_type": node.get("semantic_type", "unknown"),
                "semantic_type_label": semantic_type_label(node.get("semantic_type", "unknown")),
                "raw_text": node.get("raw_text", ""),
            }
        if args.exam in ("final", "both"):
            node = item.get("final") or {}
            row["final"] = {
                "text": scope_text(node),
                "status": node.get("status", "missing"),
                "semantic_type": node.get("semantic_type", "unknown"),
                "semantic_type_label": semantic_type_label(node.get("semantic_type", "unknown")),
                "raw_text": node.get("raw_text", ""),
            }
        rows.append(row)

    result = {
        "success": True,
        "source": {
            "record_id": record.get("record_id", ""),
            "kind": record.get("kind", ""),
            "status": record.get("status", ""),
            "curated_path": record.get("curated_path", ""),
        },
        "schema": meta["schema"],
        "city": meta["city"],
        "academic_year": meta["academic_year"],
        "semester": meta["semester"],
        "semester_label": meta["semester_label"],
        "grade_scope": meta["grade_scope"],
        "grade_scope_label": meta["grade_scope_label"],
        "grade_query": args.grade,
        "subject_query": args.subject,
        "exam": args.exam,
        "count": len(rows),
        "rows": rows,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
