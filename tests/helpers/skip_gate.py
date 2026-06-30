"""Shared skip gates for optional dependency stacks.

Replaces the inline ``python3 - <<'PY' import fastapi ...`` heredoc probes
scattered through ``scripts/check-all.sh``. Call from a migrated test module
that needs the hosted-server stack.
"""

from __future__ import annotations

import pytest

_SERVER_STACK = ("fastapi", "httpx", "jinja2", "sqlalchemy", "uvicorn")


def require_server_stack() -> None:
    """Skip the calling test unless the full hosted-server dependency stack imports."""
    for module in _SERVER_STACK:
        pytest.importorskip(module)
