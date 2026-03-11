#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from catalog_utils import datahub_root, read_json, resolve_workspace_path  # noqa: E402


def active_sources_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "active_sources.json"


def get_active_source(semester: str, kind: str, active_sources_json: str = "") -> dict:
    path = Path(active_sources_json).expanduser() if active_sources_json else active_sources_path()
    data = read_json(path, default={}) or {}
    return (((data.get("by_semester") or {}).get(semester) or {}).get(kind) or {})


def resolve_schedule_json_path(
    *,
    semester: str,
    kind: str,
    fallback_path: Path,
    active_sources_json: str = "",
) -> Path:
    item = get_active_source(semester, kind, active_sources_json=active_sources_json)
    curated_path = item.get("curated_path") or ""
    if curated_path:
        p = resolve_workspace_path(curated_path)
        if p.exists():
            return p
    return fallback_path


def build_trace_from_active_source(semester: str, kind: str, active_sources_json: str = "") -> dict:
    item = get_active_source(semester, kind, active_sources_json=active_sources_json)
    if not item:
        return {
            "semester": semester,
            "kind": kind,
            "record_id": "",
            "source_name": "",
            "archived_path": "",
            "status": "",
        }
    return {
        "semester": semester,
        "kind": kind,
        "record_id": item.get("record_id", ""),
        "source_name": item.get("source_name", ""),
        "archived_path": item.get("curated_path", "") or item.get("raw_path", ""),
        "status": "active",
    }
