#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

from catalog_utils import datahub_root, now_iso, read_json, write_json


def overrides_path() -> Path:
    return datahub_root() / "curated" / "indexes" / "user_overrides.json"


def ensure_overrides() -> dict:
    data = read_json(overrides_path(), default=None)
    if not data:
        data = {
            "schema_version": "teacher-work-datahub.user-overrides.v1",
            "teachers": {},
            "runtime": {},
        }
    data.setdefault("teachers", {})
    data.setdefault("runtime", {})
    return data


def normalize_class_name(value: str) -> str:
    text = (value or "").strip().replace(" ", "")
    if not text:
        return ""
    if text.endswith("班"):
        return text
    return f"{text}班"


def set_teacher_override(teacher: str, *, classes=None, subjects=None, note="") -> dict:
    data = ensure_overrides()
    teacher_bucket = data["teachers"].setdefault(teacher, {})
    if classes is not None:
        teacher_bucket["classes"] = sorted({normalize_class_name(x) for x in classes if x})
    if subjects is not None:
        teacher_bucket["subjects"] = sorted({(x or "").strip() for x in subjects if x})
    if note:
        teacher_bucket["note"] = note
    teacher_bucket["updated_at"] = now_iso()
    write_json(overrides_path(), data)
    return teacher_bucket


def get_teacher_override(teacher: str) -> dict | None:
    data = ensure_overrides()
    return (data.get("teachers") or {}).get(teacher)


def set_runtime_override(key: str, value):
    data = ensure_overrides()
    data["runtime"][key] = value
    write_json(overrides_path(), data)
    return data["runtime"]


def get_runtime_override(key: str, default=None):
    data = ensure_overrides()
    return (data.get("runtime") or {}).get(key, default)
