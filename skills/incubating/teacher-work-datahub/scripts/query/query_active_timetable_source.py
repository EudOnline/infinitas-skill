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

from catalog_utils import datahub_root, read_json  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--semester", required=True)
    ap.add_argument("--kind", required=True)
    args = ap.parse_args()

    p = datahub_root() / "curated" / "indexes" / "active_sources.json"
    data = read_json(p, default={}) or {}
    semesters = data.get("semesters") or data.get("by_semester") or {}
    item = ((semesters.get(args.semester) or {}).get(args.kind)) or {}
    if not item:
        raise SystemExit(f"未找到 active source: semester={args.semester}, kind={args.kind}")
    print(json.dumps(item, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
