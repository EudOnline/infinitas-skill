from __future__ import annotations

import json
import logging

from server.logging import JSONFormatter


def test_json_formatter_preserves_request_context_fields() -> None:
    record = logging.LogRecord(
        "infinitas.server.middleware",
        logging.INFO,
        __file__,
        1,
        "request completed",
        (),
        None,
    )
    record.request_id = "abc123"
    record.status_code = 200
    record.duration_ms = 1.25

    payload = json.loads(JSONFormatter().format(record))

    assert payload["message"] == "request completed"
    assert payload["extra"] == {
        "request_id": "abc123",
        "status_code": 200,
        "duration_ms": 1.25,
    }
