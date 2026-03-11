#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
from pathlib import Path

from progress_query_utils import load_json, normalize_grade_scope, normalize_semester

CITY_SLUG_MAP = {
    "太原市": "ty",
    "襄阳市": "xy",
}


def norm(value: str) -> str:
    return (value or "").strip()


def city_slug(city: str) -> str:
    c = norm(city)
    if c in CITY_SLUG_MAP:
        return CITY_SLUG_MAP[c]
    cleaned = "".join(ch.lower() for ch in c if ch.isascii() and ch.isalnum())
    return cleaned or "city"


def year_slug(academic_year: str) -> str:
    return "".join(ch for ch in norm(academic_year) if ch.isdigit()) or "year"


def ts_slug(record: dict, fallback_index: int) -> str:
    raw = norm(record.get("created_at")) or norm(record.get("updated_at"))
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 14:
        return digits[:14]
    return f"{fallback_index:03d}"


def build_key(city: str, academic_year: str, semester: str, grade_scope: str) -> str:
    return f"{norm(city)}::{norm(academic_year)}::{norm(semester)}::{norm(grade_scope)}"


def build_record_id(city: str, academic_year: str, semester: str, grade_scope: str, ts: str) -> str:
    return f"tp-{city_slug(city)}-{year_slug(academic_year)}-{norm(semester).lower()}-{norm(grade_scope)}-{ts}"


def record_sort_key(record: dict):
    status_score = 1 if norm(record.get("status")) == "active" else 0
    ts = norm(record.get("updated_at")) or norm(record.get("created_at"))
    return (status_score, ts)


def update_extracted_catalog(extracted_path: Path, record_id: str, key: str) -> None:
    if not extracted_path.exists():
        return
    try:
        data = json.loads(extracted_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    catalog = data.get("catalog") or {}
    catalog["record_id"] = record_id
    catalog["key"] = key
    data["catalog"] = catalog
    extracted_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--target-city", default="")
    parser.add_argument("--target-academic-year", default="")
    parser.add_argument("--target-semester", default="")
    parser.add_argument("--target-grade-scope", default="")
    parser.add_argument("--active-extracted-path", default="")
    parser.add_argument("--active-report-path", default="")
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    out_path = Path(args.out) if norm(args.out) else catalog_path
    data = load_json(catalog_path)
    records = data.get("records") or []

    target_key = ""
    if norm(args.target_city) and norm(args.target_academic_year) and norm(args.target_semester) and norm(args.target_grade_scope):
        target_key = build_key(
            args.target_city,
            args.target_academic_year,
            normalize_semester(args.target_semester),
            normalize_grade_scope(args.target_grade_scope),
        )

    normalized_records = []
    for idx, record in enumerate(records, start=1):
        semester = normalize_semester(record.get("semester"))
        grade_scope = normalize_grade_scope(record.get("grade_scope"))
        key = build_key(record.get("city", ""), record.get("academic_year", ""), semester, grade_scope)
        new_record = dict(record)
        new_record["semester"] = semester
        new_record["grade_scope"] = grade_scope
        new_record["record_id"] = build_record_id(record.get("city", ""), record.get("academic_year", ""), semester, grade_scope, ts_slug(record, idx))

        if target_key and key == target_key and norm(record.get("status")) == "active":
            if norm(args.active_extracted_path):
                new_record["extracted_path"] = norm(args.active_extracted_path)
            if norm(args.active_report_path):
                new_record["report_path"] = norm(args.active_report_path)

        normalized_records.append(new_record)

    grouped = {}
    for record in normalized_records:
        key = build_key(record.get("city", ""), record.get("academic_year", ""), record.get("semester", ""), record.get("grade_scope", ""))
        grouped.setdefault(key, []).append(record)

    active_index = {}
    for key, items in grouped.items():
        best = sorted(items, key=record_sort_key, reverse=True)[0]
        active_index[key] = best.get("record_id", "")

    out = {
        "version": "2.0",
        "records": normalized_records,
        "active_index": active_index,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    for record in normalized_records:
        key = build_key(record.get("city", ""), record.get("academic_year", ""), record.get("semester", ""), record.get("grade_scope", ""))
        update_extracted_catalog(Path(record.get("extracted_path", "")), record.get("record_id", ""), key)

    print(json.dumps({"out": str(out_path), "record_count": len(normalized_records), "active_keys": len(active_index)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
