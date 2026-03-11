#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

from progress_query_utils import (
    extract_entries,
    load_json,
    normalize_grade_scope,
    normalize_semester,
    normalized_record_meta,
)


def migrate_record(data: dict) -> dict:
    meta = normalized_record_meta(data)
    entries = extract_entries(data)
    out = {
        "schema_version": "2.0",
        "doc_type": "teaching_progress_total_table" if len(entries) != 1 else "teaching_progress_subject_table",
        "city": meta["city"],
        "academic_year": meta["academic_year"],
        "semester": normalize_semester(meta["semester"]),
        "grade_scope": normalize_grade_scope(meta["grade_scope"]),
        "source": {
            "file": (data.get("source") or {}).get("file", ""),
            "filename": (data.get("source") or {}).get("filename", ""),
            "status": (data.get("source") or {}).get("status", "draft"),
            "version": (data.get("source") or {}).get("version", ""),
            "updated_at": (data.get("source") or {}).get("updated_at", ""),
        },
        "catalog": data.get("catalog") or {
            "record_id": "",
            "key": f"{meta['city']}::{meta['academic_year']}::{normalize_semester(meta['semester'])}::{normalize_grade_scope(meta['grade_scope'])}",
        },
        "entries": entries,
        "warnings": data.get("warnings") or [],
        "notes": data.get("notes") or [],
        "stats": {
            "entry_count": len(entries),
        },
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="input_path", required=True)
    parser.add_argument("--out", dest="output_path", required=True)
    args = parser.parse_args()

    src = Path(args.input_path)
    out = Path(args.output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    data = load_json(src)
    migrated = migrate_record(data)
    out.write_text(json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
