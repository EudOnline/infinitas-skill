from __future__ import annotations

from pathlib import Path

import pytest

from infinitas_skill.root import resolve_repo_root


def _repo_root(path: Path) -> Path:
    path.mkdir()
    (path / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    (path / "scripts").mkdir()
    return path


@pytest.mark.parametrize(
    "env_name",
    ["INFINITAS_ROOT", "INFINITAS_REPO_ROOT", "INFINITAS_BUNDLED_REPO_PATH"],
)
def test_resolve_repo_root_honors_supported_environment_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env_name: str
) -> None:
    expected = _repo_root(tmp_path / "repo")
    for candidate in ("INFINITAS_ROOT", "INFINITAS_REPO_ROOT", "INFINITAS_BUNDLED_REPO_PATH"):
        monkeypatch.delenv(candidate, raising=False)
    monkeypatch.setenv(env_name, str(expected))

    assert resolve_repo_root() == expected.resolve()


def test_resolve_repo_root_uses_first_valid_environment_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundled = _repo_root(tmp_path / "bundle")
    monkeypatch.setenv("INFINITAS_ROOT", str(tmp_path / "missing"))
    monkeypatch.setenv("INFINITAS_BUNDLED_REPO_PATH", str(bundled))

    assert resolve_repo_root() == bundled.resolve()
