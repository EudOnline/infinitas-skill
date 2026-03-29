from __future__ import annotations

import json
from typing import Any


def dumps_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


def loads_json(payload: str, *, default: Any) -> Any:
    try:
        return json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return default
