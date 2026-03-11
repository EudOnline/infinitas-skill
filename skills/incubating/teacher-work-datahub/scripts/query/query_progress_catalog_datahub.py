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

from catalog_utils import catalog_path, read_json  # noqa: E402


def norm(v: str) -> str:
    return (v or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-json", default=str(catalog_path()))
    parser.add_argument("--city", default="")
    parser.add_argument("--academic-year", default="")
    parser.add_argument("--semester", default="")
    parser.add_argument("--grade-scope", default="")
    args = parser.parse_args()

    data = read_json(Path(args.catalog_json), default={}) or {}
    records = data.get("records") or []
    out = []
    for r in records:
        if r.get("domain") != "teaching_progress":
            continue
        meta = r.get("metadata") or {}
        if args.city and norm(meta.get("city")) != norm(args.city):
            continue
        if args.academic_year and norm(r.get("academic_year")) != norm(args.academic_year):
            continue
        if args.semester and norm(r.get("semester")) != norm(args.semester):
            continue
        if args.grade_scope and norm(meta.get("grade_scope")) != norm(args.grade_scope):
            continue
        out.append(r)

    out.sort(key=lambda x: (x.get("status") == "active", x.get("parsed_at", ""), x.get("ingested_at", "")), reverse=True)
    print(json.dumps({"count": len(out), "records": out}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
