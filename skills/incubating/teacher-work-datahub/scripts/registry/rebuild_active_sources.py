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

from catalog_utils import datahub_root, ensure_catalog, write_json  # noqa: E402


def output_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "active_sources.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="可选输出路径")
    args = ap.parse_args()

    catalog = ensure_catalog()
    result = {
        "schema_version": "teacher-work-datahub.active-sources.v1",
        "by_semester": {},
    }

    for rec in catalog.get("records", []):
        if rec.get("status") != "active":
            continue
        semester = rec.get("semester") or "UNKNOWN"
        kind = rec.get("kind") or "unknown_kind"
        bucket = result["by_semester"].setdefault(semester, {})
        bucket[kind] = {
            "record_id": rec.get("record_id"),
            "source_name": rec.get("source_name"),
            "raw_path": rec.get("raw_path"),
            "curated_path": rec.get("curated_path"),
            "academic_year": rec.get("academic_year"),
            "kind": kind,
            "domain": rec.get("domain"),
        }

    out = Path(args.out).expanduser() if args.out else output_path()
    write_json(out, result)
    print(json.dumps({"success": True, "output_path": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
