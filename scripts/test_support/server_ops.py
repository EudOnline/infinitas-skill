"""Compatibility shim.

The real implementation moved to ``tests/helpers/ops_support/server_ops.py``.
Un-migrated scripts still do ``from test_support.server_ops import ...`` (with
``scripts/`` on ``sys.path[0]``); this re-exports from the canonical location.
Removed in Phase 4 once every script has migrated.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])  # scripts/test_support/x.py -> repo root
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tests.helpers.ops_support.server_ops import (  # noqa: F401
    HealthServer,
    prepare_artifacts,
    prepare_repo,
    prepare_sqlite_db,
    run_command,
)
