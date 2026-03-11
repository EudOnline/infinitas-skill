#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import json
import random
import string
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import os


SCHEMA_VERSION = "teacher-work-datahub.sources.v1"


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def workspace_root() -> Path:
    override = os.getenv("TEACHER_WORK_DATAHUB_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return project_root()


def datahub_root() -> Path:
    return workspace_root() / "data" / "teacher-work-datahub"


def catalog_path() -> Path:
    return datahub_root() / "catalog" / "sources.json"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_catalog() -> Dict[str, Any]:
    catalog = read_json(catalog_path(), default=None)
    if not catalog:
        catalog = {
            "schema_version": SCHEMA_VERSION,
            "records": [],
        }
    if "schema_version" not in catalog:
        catalog["schema_version"] = SCHEMA_VERSION
    if "records" not in catalog:
        catalog["records"] = []
    return catalog


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def new_record_id(prefix: str = "src") -> str:
    suffix = "".join(random.choices(string.hexdigits.lower(), k=12))
    return f"{prefix}-{suffix}"


def normalize_status(status: str) -> str:
    value = (status or "").strip().lower()
    if value not in {"active", "archived", "ingested"}:
        return "ingested"
    return value


def mark_previous_active_archived(
    records: list[dict],
    *,
    kind: str,
    semester: str,
    new_record_id: str,
) -> list[str]:
    archived = []
    for rec in records:
        if rec.get("kind") == kind and rec.get("semester") == semester and rec.get("status") == "active":
            rec["status"] = "archived"
            rec["superseded_by"] = new_record_id
            notes = rec.get("notes", "")
            if "默认替换策略" not in notes:
                rec["notes"] = (notes + " 同类型同学期旧版本（默认替换策略保留归档，不作为当前生效版本）。").strip()
            archived.append(rec.get("record_id", ""))
    return archived


def find_record_by_fingerprint(records: list[dict], fingerprint: str, kind: str, semester: str) -> dict | None:
    for rec in records:
        if (
            rec.get("fingerprint") == fingerprint
            and rec.get("kind") == kind
            and rec.get("semester") == semester
        ):
            return rec
    return None


def to_workspace_relative(path: Path) -> str:
    root = workspace_root()
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def resolve_workspace_path(path_like: str | Path) -> Path:
    p = Path(path_like)
    if p.is_absolute():
        return p
    return workspace_root() / p
