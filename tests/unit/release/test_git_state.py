from __future__ import annotations

import subprocess
from pathlib import Path

from infinitas_skill.release.git_state import ahead_behind, split_remote


def test_split_remote_prefers_upstream_remote_name() -> None:
    assert split_remote("origin/main", "backup") == "origin"
    assert split_remote(None, "backup") == "backup"


def test_ahead_behind_parses_left_right_counts(monkeypatch, tmp_path: Path) -> None:
    def fake_git(root, *args, check=True, extra_config=None):
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=0,
            stdout="3 1\n",
            stderr="",
        )

    monkeypatch.setattr("infinitas_skill.release.git_state.git", fake_git)

    ahead, behind = ahead_behind(tmp_path, "origin/main")

    assert ahead == 3
    assert behind == 1
