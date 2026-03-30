from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from test_support.server_ops import prepare_artifacts, prepare_repo, prepare_sqlite_db


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RepoState:
    root: Path
    repo: Path
    db_path: Path
    artifact_dir: Path


def create_repo_state(base: Path) -> RepoState:
    return RepoState(
        root=ROOT,
        repo=prepare_repo(base),
        db_path=prepare_sqlite_db(base),
        artifact_dir=prepare_artifacts(base),
    )


@pytest.fixture
def repo_state(tmp_path: Path) -> RepoState:
    return create_repo_state(tmp_path)
