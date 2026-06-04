"""Shared data-access helpers for CLI-side server operations.

This module provides a thin abstraction over server models so that
``src/infinitas_skill/server/`` files can access database models without
importing from ``server.*`` at module load time, avoiding circular
dependencies between the library and the application package.

All imports from ``server.*`` are deferred to function-call time via
lazy accessor functions.
"""
from __future__ import annotations

import json
from typing import Any


def parse_json_payload(raw: str | None) -> dict[str, Any]:
    """Parse a JSON string into a dict, returning ``{}`` on any failure.

    Consolidates the duplicated ``_payload`` helpers that previously
    appeared in 4 separate files.
    """
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def get_audit_event_model():
    """Return the ``AuditEvent`` SQLAlchemy model class (lazy import)."""
    from server.models import AuditEvent
    return AuditEvent


def get_job_model():
    """Return the ``Job`` SQLAlchemy model class (lazy import)."""
    from server.models import Job
    return Job
