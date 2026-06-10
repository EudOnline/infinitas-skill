from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dumps_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


def loads_json(payload: str, *, default: Any) -> Any:
    try:
        return json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return default


def read_json_file(path: Path) -> dict:
    """Read and parse a JSON file, returning ``{}`` on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
