"""Inspection notification delivery helpers for hosted server operations."""

from __future__ import annotations

import json
from pathlib import Path
from urllib import error, request


def deliver_inspect_webhook(summary: dict, url: str) -> None:
    notification = summary["notification"]["webhook"]
    notification["attempted"] = True
    notification["url"] = url
    payload = json.dumps(summary, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            notification["status_code"] = response.status
            notification["delivered"] = 200 <= response.status < 300
    except error.HTTPError as exc:
        notification["status_code"] = exc.code
        notification["error"] = f"HTTP {exc.code}"
    except error.URLError as exc:
        notification["error"] = str(exc.reason)
    except Exception as exc:  # pragma: no cover - defensive fallback
        notification["error"] = str(exc)


def write_inspect_fallback(summary: dict, path_text: str) -> None:
    notification = summary["notification"]["fallback"]
    path = Path(path_text)
    notification["attempted"] = True
    notification["path"] = str(path)
    notification["wrote"] = True
    notification["error"] = ""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        notification["wrote"] = False
        notification["error"] = str(exc)


__all__ = ["deliver_inspect_webhook", "write_inspect_fallback"]
