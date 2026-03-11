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

from catalog_utils import datahub_root, read_json, write_json  # noqa: E402
from progress_query_utils import normalize_grade_scope, normalize_semester  # noqa: E402


def semester_context_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "semester_context.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="")
    parser.add_argument("--academic-year", default="")
    parser.add_argument("--semester", default="")
    parser.add_argument("--grade-scope", default="")
    args = parser.parse_args()

    path = semester_context_path()
    data = read_json(path, default={}) or {}
    current = data.setdefault("current", {})

    if args.city:
        current["city"] = args.city
    if args.academic_year:
        current["academic_year"] = args.academic_year
    if args.semester:
        current["semester"] = normalize_semester(args.semester)
    if args.grade_scope:
        current["grade_scope"] = normalize_grade_scope(args.grade_scope)

    write_json(path, data)
    print(json.dumps({"success": True, "path": str(path), "current": current}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
