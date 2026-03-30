from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

_LOCAL_STATE_PATTERNS = (
    ".git",
    ".venv",
    ".planning",
    ".worktrees",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
    "*.pyc",
)


def copy_repo_without_local_state(base: Path) -> Path:
    destination = base / "repo"
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(*_LOCAL_STATE_PATTERNS),
    )
    return destination
