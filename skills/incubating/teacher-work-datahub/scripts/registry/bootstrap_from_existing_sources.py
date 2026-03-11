#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OLD = ROOT / "data" / "schedules" / "catalog" / "sources.json"
NEW = ROOT / "data" / "teacher-work-datahub" / "catalog" / "sources.json"


def main() -> None:
    if not OLD.exists():
        raise SystemExit(f"旧 sources 不存在: {OLD}")

    old = json.loads(OLD.read_text(encoding="utf-8"))
    out = {
        "schema_version": "teacher-work-datahub.sources.v1",
        "records": [],
    }

    for rec in old.get("records", []):
        kind = rec.get("kind", "")
        if kind in {"teacher_allocation", "grade_schedule_with_selfstudy", "school_schedule_no_selfstudy"}:
            domain = "teacher_allocation" if kind == "teacher_allocation" else "schedules"
            path_key = "archived_path" if rec.get("archived_path") else "source_path"
            raw_or_curated = rec.get(path_key, "")
            out["records"].append(
                {
                    "record_id": rec.get("record_id"),
                    "domain": domain,
                    "kind": kind,
                    "academic_year": "2025-2026",
                    "semester": rec.get("semester", ""),
                    "status": rec.get("status", "ingested"),
                    "source_name": rec.get("source_name", ""),
                    "raw_path": raw_or_curated,
                    "curated_path": (
                        "data/schedules/teacher_allocation_202603_parsed_allgrades.json"
                        if kind == "teacher_allocation" and rec.get("semester") == "S2" and rec.get("status") == "active"
                        else (
                            "data/schedules/teacher_allocation_202509_unmerged_structured.json"
                            if kind == "teacher_allocation" and rec.get("semester") == "S1" and rec.get("status") == "active"
                            else (
                                raw_or_curated if kind == "grade_schedule_with_selfstudy" else ""
                            )
                        )
                    ),
                    "report_paths": [],
                    "source_mtime": rec.get("source_mtime", ""),
                    "ingested_at": rec.get("first_seen", ""),
                    "parsed_at": rec.get("last_synced", ""),
                    "fingerprint": "",
                    "size_bytes": rec.get("size_bytes", 0),
                    "superseded_by": rec.get("superseded_by"),
                    "notes": rec.get("notes", ""),
                    "metadata": {
                        "migrated_from": "data/schedules/catalog/sources.json"
                    },
                }
            )

    NEW.parent.mkdir(parents=True, exist_ok=True)
    NEW.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(NEW))


if __name__ == "__main__":
    main()
