from __future__ import annotations

import json
from pathlib import Path
from urllib import error

from infinitas_skill.server.inspection_notifications import (
    deliver_inspect_webhook,
    write_inspect_fallback,
)


def _base_summary() -> dict:
    return {
        "notification": {
            "webhook": {
                "attempted": False,
                "delivered": False,
                "url": "",
                "status_code": None,
                "error": "",
            },
            "fallback": {
                "attempted": False,
                "wrote": False,
                "path": "",
                "error": "",
            },
        }
    }


def test_deliver_inspect_webhook_marks_success(monkeypatch) -> None:
    class _Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=10: _Response())
    summary = _base_summary()

    deliver_inspect_webhook(summary, "https://example.test/hook")

    webhook = summary["notification"]["webhook"]
    assert webhook["attempted"] is True
    assert webhook["url"] == "https://example.test/hook"
    assert webhook["status_code"] == 204
    assert webhook["delivered"] is True


def test_deliver_inspect_webhook_records_urlerror(monkeypatch) -> None:
    def _raise_urlerror(_req, timeout=10):
        raise error.URLError("network-down")

    monkeypatch.setattr("urllib.request.urlopen", _raise_urlerror)
    summary = _base_summary()

    deliver_inspect_webhook(summary, "https://example.test/hook")

    webhook = summary["notification"]["webhook"]
    assert webhook["attempted"] is True
    assert webhook["delivered"] is False
    assert webhook["status_code"] is None
    assert "network-down" in webhook["error"]


def test_write_inspect_fallback_writes_json_file(tmp_path: Path) -> None:
    summary = _base_summary()
    target = tmp_path / "nested" / "inspect.json"

    write_inspect_fallback(summary, str(target))

    fallback = summary["notification"]["fallback"]
    assert fallback["attempted"] is True
    assert fallback["wrote"] is True
    assert fallback["path"] == str(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["notification"]["fallback"]["path"] == str(target)


def test_write_inspect_fallback_records_write_failure(monkeypatch, tmp_path: Path) -> None:
    def _raise_write_text(self, text, encoding="utf-8"):
        raise OSError("disk-full")

    monkeypatch.setattr(Path, "write_text", _raise_write_text)
    summary = _base_summary()
    target = tmp_path / "inspect.json"

    write_inspect_fallback(summary, str(target))

    fallback = summary["notification"]["fallback"]
    assert fallback["attempted"] is True
    assert fallback["wrote"] is False
    assert "disk-full" in fallback["error"]
