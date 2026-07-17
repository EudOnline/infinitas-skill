"""Centralized logging configuration for the infinitas server.

Provides structured logging with consistent formatting across all modules.
Import and use ``get_logger`` to obtain a module-scoped logger.

Supports two output formats:
- ``text`` (default): Human-readable timestamp + level + message
- ``json``: Structured JSON for log aggregation (ELK, Datadog, etc.)

Configure via environment variable::

    INFINITAS_LOG_FORMAT=json
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

_TEXT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

_root_initialized = False


class JSONFormatter(logging.Formatter):
    """Emit log records as structured JSON objects.

    Output format::

        {
            "timestamp": "2026-06-11T12:00:00+0000",
            "level": "INFO",
            "logger": "infinitas.server.app",
            "message": "request completed",
            "extra": {...}
        }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from the record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "relativeCreated",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "pathname",
                "filename",
                "module",
                "levelno",
                "levelname",
                "msecs",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            ):
                if not key.startswith("_"):
                    extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def _ensure_root_handler() -> None:
    """Attach a stderr StreamHandler to the root infinitas logger once."""
    global _root_initialized
    if _root_initialized:
        return
    root = logging.getLogger("infinitas")
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(handler)
    _root_initialized = True


def configure_logging(
    *,
    level: str | None = None,
    log_format: str | None = None,
    log_file: Path | None = None,
) -> None:
    """Configure the infinitas logging subsystem.

    Parameters
    ----------
    level:
        Override log level (e.g. ``"DEBUG"``). Falls back to the
        ``INFINITAS_LOG_LEVEL`` environment variable, then ``"INFO"``.
    log_format:
        Output format: ``"text"`` (default) or ``"json"``. Falls back to
        the ``INFINITAS_LOG_FORMAT`` environment variable.
    log_file:
        Optional file path for persistent log output.
    """
    import os

    _ensure_root_handler()
    effective_level = (level or os.environ.get("INFINITAS_LOG_LEVEL") or "INFO").upper()
    effective_format = (log_format or os.environ.get("INFINITAS_LOG_FORMAT") or "text").lower()

    root = logging.getLogger("infinitas")
    root.setLevel(getattr(logging, effective_level, logging.INFO))

    # Update existing handler formatters
    if effective_format == "json":
        json_formatter = JSONFormatter()
        for handler in root.handlers:
            handler.setFormatter(json_formatter)

    if log_file is not None:
        fh = logging.FileHandler(str(log_file))
        if effective_format == "json":
            fh.setFormatter(JSONFormatter())
        else:
            fh.setFormatter(logging.Formatter(_TEXT_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``infinitas`` namespace.

    Usage::

        from server.logging import get_logger
        log = get_logger(__name__)
        log.info("request completed")
    """
    _ensure_root_handler()
    if not name.startswith("infinitas."):
        name = f"infinitas.{name}"
    return logging.getLogger(name)
