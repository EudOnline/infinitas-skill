from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from server.runtime_repo import RuntimeRepoError, ensure_runtime_repo, is_git_repo


def _bundled_snapshot(tmp_path: Path) -> Path:
    bundled = tmp_path / "bundled"
    (bundled / "catalog").mkdir(parents=True, exist_ok=True)
    (bundled / "README.md").write_text("bundled snapshot\n", encoding="utf-8")
    (bundled / "catalog" / "index.json").write_text("{}\n", encoding="utf-8")
    (bundled / ".state").mkdir(exist_ok=True)
    (bundled / ".state" / "ignored.db").write_text("ignore", encoding="utf-8")
    return bundled


def _bootstrap(tmp_path: Path, **kwargs):
    return ensure_runtime_repo(
        bundled_repo_path=_bundled_snapshot(tmp_path),
        repo_path=tmp_path / "runtime",
        repo_lock_path=tmp_path / "locks" / "repo.lock",
        **kwargs,
    )


def test_empty_runtime_repo_is_seeded_as_git_worktree(tmp_path: Path) -> None:
    result = _bootstrap(tmp_path, branch="release")
    repo = tmp_path / "runtime"

    assert result.seeded is True
    assert result.branch == "release"
    assert is_git_repo(repo)
    assert (repo / "README.md").read_text(encoding="utf-8") == "bundled snapshot\n"
    assert (repo / "catalog" / "index.json").is_file()
    assert not (repo / ".state").exists()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    assert branch == "release"


def test_existing_git_repo_is_reused_and_origin_is_idempotent(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    repo = tmp_path / "runtime"
    (repo / "runtime-only.txt").write_text("preserve\n", encoding="utf-8")

    first = _bootstrap(tmp_path, origin_url="ssh://git@example.test/registry.git")
    second = _bootstrap(tmp_path, origin_url="ssh://git@example.test/registry.git")

    assert first.seeded is False and first.origin_configured is True
    assert second.seeded is False and second.origin_configured is False
    assert (repo / "runtime-only.txt").read_text(encoding="utf-8") == "preserve\n"
    origin = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    assert origin == "ssh://git@example.test/registry.git"


def test_non_git_nonempty_runtime_repo_is_rejected_without_reset(tmp_path: Path) -> None:
    repo = tmp_path / "runtime"
    repo.mkdir()
    (repo / "operator-data.txt").write_text("preserve me", encoding="utf-8")

    with pytest.raises(RuntimeRepoError, match="not a git worktree"):
        _bootstrap(tmp_path)

    assert (repo / "operator-data.txt").read_text(encoding="utf-8") == "preserve me"


def test_allow_reset_replaces_non_git_directory_with_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "runtime"
    repo.mkdir()
    (repo / "stale.txt").write_text("stale", encoding="utf-8")

    result = _bootstrap(tmp_path, allow_reset=True)

    assert result.seeded is True
    assert not (repo / "stale.txt").exists()
    assert (repo / "README.md").is_file()
    assert is_git_repo(repo)


def test_missing_bundled_snapshot_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(RuntimeRepoError, match="bundled repo path does not exist"):
        ensure_runtime_repo(
            bundled_repo_path=tmp_path / "missing",
            repo_path=tmp_path / "runtime",
            repo_lock_path=tmp_path / "locks" / "repo.lock",
        )
