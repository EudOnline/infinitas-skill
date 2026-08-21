from __future__ import annotations

from pathlib import Path

import pytest

from infinitas_skill.agent.profile import (
    finalize_profile_rotation,
    pending_rotation_path,
    read_profile,
    replace_profile_credentials,
    stage_profile_rotation,
    write_profile,
)


def test_profile_write_is_atomic_and_preserves_existing_credentials(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    original = {
        "base_url": "https://registry.example.test",
        "api_key": "agt_original",
        "status_key": "status_original",
    }
    path = write_profile("default", original)

    updated = {**original, "principal_slug": "agent-one"}
    assert write_profile("default", updated) == path
    assert read_profile("default")["principal_slug"] == "agent-one"
    with pytest.raises(ValueError, match="refusing to replace"):
        write_profile("default", {**updated, "api_key": "agt_replacement"})

    rotated = {**updated, "api_key": "agt_replacement"}
    replace_profile_credentials("default", rotated, expected_api_key="agt_original")
    assert read_profile("default")["api_key"] == "agt_replacement"


def test_profile_write_rejects_symlinked_target_and_parent(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    agents = config / "infinitas" / "agents"
    agents.mkdir(parents=True)
    target = tmp_path / "elsewhere.json"
    target.write_text("{}", encoding="utf-8")
    (agents / "default.json").symlink_to(target)
    with pytest.raises(ValueError, match="must not be a symlink"):
        write_profile("default", {"api_key": "agt_value"})

    (agents / "default.json").unlink()
    agents.rmdir()
    agents.symlink_to(tmp_path / "real-agents", target_is_directory=True)
    (tmp_path / "real-agents").mkdir()
    with pytest.raises(ValueError, match="must not be a symlink"):
        write_profile("default", {"api_key": "agt_value"})


def test_pending_rotation_survives_failure_and_can_be_finalized(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    original = {"base_url": "https://registry.example.test", "api_key": "agt_original"}
    replacement = {**original, "api_key": "agt_replacement", "fingerprint": "a" * 16}
    write_profile("default", original)

    staged, created = stage_profile_rotation(
        "default", replacement, expected_api_key="agt_original"
    )
    assert created is True
    assert staged == replacement
    assert pending_rotation_path("default").stat().st_mode & 0o777 == 0o600
    assert read_profile("default")["api_key"] == "agt_original"

    repeated, created = stage_profile_rotation(
        "default", {**replacement, "api_key": "agt_other"}, expected_api_key="agt_original"
    )
    assert created is False
    assert repeated == replacement
    finalize_profile_rotation("default")
    assert read_profile("default")["api_key"] == "agt_replacement"
    assert not pending_rotation_path("default").exists()
