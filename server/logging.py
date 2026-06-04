"""Centralized logging configuration for the infinitas server.

Provides structured logging with consistent formatting across all modules.
Import and use ``get_logger`` to obtain a module-scoped logger.
"""
from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

_root_initialized = False


def _ensure_root_handler() -> None:
    """Attach a stderr StreamHandler to the root infinitas logger once."""
    global _root_initialized
    if _root_initialized:
        return
    root = logging.getLogger("infinitas")
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(handler)
    _root_initialized = True


def configure_logging(*, level: str | None = None, log_file: Path | None = None) -> None:
    """Configure the infinitas logging subsystem.

    Parameters
    ----------
    level:
        Override log level (e.g. ``"DEBUG"``). Falls back to the
        ``INFINITAS_LOG_LEVEL`` environment variable, then ``"INFO"``.
    log_file:
        Optional file path for persistent log output.
    """
    import os

    _ensure_root_handler()
    effective = (
        level
        or os.environ.get("INFINITAS_LOG_LEVEL")
        or "INFO"
    ).upper()
    root = logging.getLogger("infinitas")
    root.setLevel(getattr(logging, effective, logging.INFO))

    if log_file is not None:
        fh = logging.FileHandler(str(log_file))
        fh.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
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
