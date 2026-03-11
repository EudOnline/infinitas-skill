#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from catalog_utils import catalog_path, datahub_root, read_json, write_json  # noqa: E402


def output_path() -> Path:
    return datahub_root() / "curated" / "lineage" / "source_lineage.json"


def main() -> None:
    catalog = read_json(catalog_path(), default={}) or {}
    records = catalog.get("records") or []
    lineage = {
        "schema_version": "teacher-work-datahub.lineage.v1",
        "records": [],
    }
    for rec in records:
        lineage["records"].append(
            {
                "record_id": rec.get("record_id", ""),
                "domain": rec.get("domain", ""),
                "kind": rec.get("kind", ""),
                "semester": rec.get("semester", ""),
                "status": rec.get("status", ""),
                "source_name": rec.get("source_name", ""),
                "raw_path": rec.get("raw_path", ""),
                "curated_path": rec.get("curated_path", ""),
                "report_paths": rec.get("report_paths", []),
                "superseded_by": rec.get("superseded_by"),
                "metadata": rec.get("metadata", {}),
            }
        )
    write_json(output_path(), lineage)
    print(json.dumps({"success": True, "count": len(lineage['records']), "output_path": str(output_path())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
