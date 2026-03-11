#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from datetime import datetime
from pathlib import Path


SEMESTER_MAP = {
    "S1": "S1",
    "s1": "S1",
    "第一学期": "S1",
    "上学期": "S1",
    "S2": "S2",
    "s2": "S2",
    "第二学期": "S2",
    "下学期": "S2",
}

GRADE_SCOPE_MAP = {
    "primary": "primary",
    "小学": "primary",
    "junior": "junior",
    "初中": "junior",
    "highschool": "highschool",
    "高中": "highschool",
}

CITY_SLUG_MAP = {
    "太原市": "ty",
    "襄阳市": "xy",
}


def norm(value: str) -> str:
    return (value or "").strip()


def now_local() -> datetime:
    return datetime.now().astimezone()


def now_iso() -> str:
    return now_local().isoformat(timespec="seconds")


def normalize_semester(value: str) -> str:
    v = norm(value)
    return SEMESTER_MAP.get(v, v)


def normalize_grade_scope(value: str) -> str:
    v = norm(value)
    return GRADE_SCOPE_MAP.get(v, v)


def city_slug(city: str) -> str:
    c = norm(city)
    if c in CITY_SLUG_MAP:
        return CITY_SLUG_MAP[c]
    cleaned = "".join(ch.lower() for ch in c if ch.isascii() and ch.isalnum())
    return cleaned or "city"


def year_slug(academic_year: str) -> str:
    return "".join(ch for ch in norm(academic_year) if ch.isdigit()) or "year"


def build_key(city: str, academic_year: str, semester: str, grade_scope: str) -> str:
    return f"{norm(city)}::{norm(academic_year)}::{norm(semester)}::{norm(grade_scope)}"


def build_record_id(city: str, academic_year: str, semester: str, grade_scope: str, ts: datetime) -> str:
    return f"tp-{city_slug(city)}-{year_slug(academic_year)}-{norm(semester).lower()}-{norm(grade_scope)}-{ts.strftime('%Y%m%d%H%M%S')}"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def update_extracted_catalog(extracted_path: Path, record_id: str, key: str) -> None:
    if not extracted_path.exists():
        return
    data = json.loads(extracted_path.read_text(encoding="utf-8"))
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
    parser.add_argument("--city", required=True)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--semester", required=True)
    parser.add_argument("--grade-scope", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--extracted-path", required=True)
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--kind", default="teaching_progress_total_table")
    parser.add_argument("--status", default="active")
    args = parser.parse_args()

    semester = normalize_semester(args.semester)
    grade_scope = normalize_grade_scope(args.grade_scope)
    if not semester:
        parser.error("invalid --semester")
    if not grade_scope:
        parser.error("invalid --grade-scope")

    catalog_path = Path(args.catalog)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    data = load_json(catalog_path, {"version": "2.0", "records": [], "active_index": {}})
    records = data.get("records") or []
    active_index = data.get("active_index") or {}

    key = build_key(args.city, args.academic_year, semester, grade_scope)
    prev_active_id = active_index.get(key, "")
    ts = now_local()

    for rec in records:
        if rec.get("record_id") == prev_active_id:
            rec["status"] = "archived"
            rec["updated_at"] = now_iso()

    record_id = build_record_id(args.city, args.academic_year, semester, grade_scope, ts)
    status = norm(args.status) or "active"
    record = {
        "record_id": record_id,
        "city": norm(args.city),
        "academic_year": norm(args.academic_year),
        "semester": semester,
        "grade_scope": grade_scope,
        "source_name": norm(args.source_name),
        "source_path": norm(args.source_path),
        "extracted_path": norm(args.extracted_path),
        "report_path": norm(args.report_path),
        "status": status,
        "kind": norm(args.kind) or "teaching_progress_total_table",
        "created_at": ts.isoformat(timespec="seconds"),
        "updated_at": ts.isoformat(timespec="seconds"),
    }
    records.append(record)
    if status == "active":
        active_index[key] = record_id
    elif prev_active_id == record_id:
        active_index.pop(key, None)

    out = {
        "version": data.get("version", "2.0"),
        "records": records,
        "active_index": active_index,
    }
    catalog_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    update_extracted_catalog(Path(args.extracted_path), record_id, key)

    print(
        json.dumps(
            {
                "record_id": record_id,
                "key": key,
                "prev_active_id": prev_active_id,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
