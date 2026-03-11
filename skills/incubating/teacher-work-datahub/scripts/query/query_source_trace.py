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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-root", default="")
    ap.add_argument("--record-id", default="")
    ap.add_argument("--domain", default="")
    ap.add_argument("--kind", default="")
    ap.add_argument("--semester", default="")
    ap.add_argument("--status", default="")
    ap.add_argument("--catalog-json", default=str(catalog_path()))
    args = ap.parse_args()
    if args.workspace_root:
        import os
        os.environ["TEACHER_WORK_DATAHUB_ROOT"] = str(Path(args.workspace_root).expanduser().resolve())

    data = read_json(Path(args.catalog_json), default={}) or {}
    records = data.get("records") or []

    result = []
    for rec in records:
        if args.record_id and rec.get("record_id") != args.record_id:
            continue
        if args.domain and rec.get("domain") != args.domain:
            continue
        if args.kind and rec.get("kind") != args.kind:
            continue
        if args.semester and rec.get("semester") != args.semester:
            continue
        if args.status and rec.get("status") != args.status:
            continue
        result.append(rec)

    print(json.dumps({"success": True, "count": len(result), "records": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
