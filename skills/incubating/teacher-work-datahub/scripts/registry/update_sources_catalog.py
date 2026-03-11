#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from catalog_utils import (  # noqa: E402
    catalog_path,
    ensure_catalog,
    find_record_by_fingerprint,
    mark_previous_active_archived,
    new_record_id,
    normalize_status,
    now_iso,
    sha256_file,
    to_workspace_relative,
    write_json,
)


def file_mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().replace(microsecond=0).isoformat()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True, help="如 teacher_allocation / schedules / teaching_progress")
    ap.add_argument("--kind", required=True, help="如 teacher_allocation / grade_schedule_with_selfstudy")
    ap.add_argument("--academic-year", required=True, help="如 2025-2026")
    ap.add_argument("--semester", required=True, help="如 S1 / S2")
    ap.add_argument("--source-name", required=True, help="原始来源名")
    ap.add_argument("--raw-path", required=True, help="raw 层文件路径")
    ap.add_argument("--curated-path", default="", help="curated 层结构化结果路径")
    ap.add_argument("--status", default="active", help="active / archived / ingested")
    ap.add_argument("--metadata-json", default="{}", help="附加 metadata JSON")
    ap.add_argument("--parallel-allowed", action="store_true", help="允许同类型+同学期并行 active")
    args = ap.parse_args()

    raw_path = Path(args.raw_path).expanduser().resolve()
    curated_path = Path(args.curated_path).expanduser().resolve() if args.curated_path else None

    if not raw_path.exists():
        raise SystemExit(f"raw-path 不存在: {raw_path}")

    try:
        metadata = json.loads(args.metadata_json or "{}")
        if not isinstance(metadata, dict):
            raise ValueError("metadata-json 必须是 JSON object")
    except Exception as exc:
        raise SystemExit(f"metadata-json 非法: {exc}") from exc

    catalog = ensure_catalog()
    records = catalog["records"]

    fingerprint = sha256_file(raw_path)
    existing = find_record_by_fingerprint(records, fingerprint, args.kind, args.semester)
    if existing:
        if curated_path:
            existing["curated_path"] = to_workspace_relative(curated_path)
            existing["parsed_at"] = now_iso()
        if args.source_name:
            existing["source_name"] = args.source_name
        existing["last_seen"] = now_iso()
        if metadata:
            existing.setdefault("metadata", {}).update(metadata)
        write_json(catalog_path(), catalog)
        print(
            json.dumps(
                {
                    "success": True,
                    "record_id": existing.get("record_id"),
                    "status": existing.get("status"),
                    "deduplicated": True,
                    "catalog_path": str(catalog_path()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    record_id = new_record_id()
    status = normalize_status(args.status)

    archived_records = []
    if status == "active" and not args.parallel_allowed:
        archived_records = mark_previous_active_archived(
            records,
            kind=args.kind,
            semester=args.semester,
            new_record_id=record_id,
        )

    source_stat = raw_path.stat()

    record = {
        "record_id": record_id,
        "domain": args.domain,
        "kind": args.kind,
        "academic_year": args.academic_year,
        "semester": args.semester,
        "status": status,
        "source_name": args.source_name,
        "raw_path": to_workspace_relative(raw_path),
        "curated_path": to_workspace_relative(curated_path) if curated_path else "",
        "report_paths": [],
        "source_mtime": file_mtime_iso(raw_path),
        "ingested_at": now_iso(),
        "parsed_at": now_iso() if curated_path else "",
        "fingerprint": fingerprint,
        "size_bytes": source_stat.st_size,
        "superseded_by": None,
        "notes": "",
        "metadata": metadata,
    }
    if args.parallel_allowed:
        record["metadata"]["parallel_allowed"] = True

    records.append(record)
    write_json(catalog_path(), catalog)

    print(
        json.dumps(
            {
                "success": True,
                "record_id": record_id,
                "status": status,
                "archived_records": archived_records,
                "catalog_path": str(catalog_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
