#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OLD = ROOT / "data" / "teaching-progress" / "catalog" / "sources.json"
NEW = ROOT / "data" / "teacher-work-datahub" / "catalog" / "sources.json"
SEM_CTX = ROOT / "data" / "teacher-work-datahub" / "curated" / "indexes" / "semester_context.json"
OLD_DEFAULTS = ROOT / "data" / "teaching-progress" / "context" / "defaults.json"


def main() -> None:
    if not OLD.exists():
        raise SystemExit(f"旧 teaching-progress sources 不存在: {OLD}")
    if not NEW.exists():
        raise SystemExit(f"新 datahub sources 不存在: {NEW}")

    old = json.loads(OLD.read_text(encoding="utf-8"))
    new = json.loads(NEW.read_text(encoding="utf-8"))
    existing = {rec.get("record_id"): rec for rec in (new.get("records") or [])}
    active_ids = set((old.get("active_index") or {}).values())

    for rec in old.get("records", []):
        rid = rec.get("record_id")
        migrated = {
            "record_id": rid,
            "domain": "teaching_progress",
            "kind": rec.get("kind", "teaching_progress_total_table"),
            "academic_year": rec.get("academic_year", ""),
            "semester": rec.get("semester", ""),
            "status": ("active" if rid in active_ids else rec.get("status", "ingested")),
            "source_name": rec.get("source_name", ""),
            "raw_path": rec.get("source_path", ""),
            "curated_path": rec.get("extracted_path", ""),
            "report_paths": [rec.get("report_path", "")] if rec.get("report_path") else [],
            "source_mtime": rec.get("updated_at", ""),
            "ingested_at": rec.get("created_at", ""),
            "parsed_at": rec.get("updated_at", ""),
            "fingerprint": "",
            "size_bytes": 0,
            "superseded_by": None,
            "notes": "",
            "metadata": {
                "migrated_from": "data/teaching-progress/catalog/sources.json",
                "city": rec.get("city", ""),
                "grade_scope": rec.get("grade_scope", ""),
            },
        }
        if rid in existing:
            existing[rid].update(migrated)
        else:
            new["records"].append(migrated)
            existing[rid] = migrated

    NEW.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")

    if OLD_DEFAULTS.exists() and SEM_CTX.exists():
        defaults = json.loads(OLD_DEFAULTS.read_text(encoding="utf-8"))
        ctx = json.loads(SEM_CTX.read_text(encoding="utf-8"))
        current = ctx.setdefault("current", {})
        if defaults.get("city"):
            current["city"] = defaults.get("city")
        if defaults.get("academic_year"):
            current["academic_year"] = defaults.get("academic_year")
        if defaults.get("semester"):
            current["semester"] = defaults.get("semester")
        if defaults.get("grade_scope"):
            current["grade_scope"] = defaults.get("grade_scope")
        SEM_CTX.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")

    print(str(NEW))


if __name__ == "__main__":
    main()
