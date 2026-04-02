from __future__ import annotations

import json
from pathlib import Path

import pytest

from infinitas_skill.release.git_state import ReleaseError
from infinitas_skill.release.release_resolution import expected_skill_tag, resolve_skill


def test_resolve_skill_prefers_explicit_directory(tmp_path: Path) -> None:
    skill_dir = tmp_path / "custom-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "_meta.json").write_text(
        json.dumps({"name": "custom-skill", "version": "1.0.0"}),
        encoding="utf-8",
    )

    resolved = resolve_skill(tmp_path, str(skill_dir))

    assert resolved == skill_dir.resolve()


def test_resolve_skill_searches_stage_directories(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "active" / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "_meta.json").write_text(
        json.dumps({"name": "demo-skill", "version": "2.3.4"}),
        encoding="utf-8",
    )

    resolved = resolve_skill(tmp_path, "demo-skill")

    assert resolved == skill_dir.resolve()


def test_resolve_skill_raises_for_unknown_target(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match="cannot resolve skill: missing"):
        resolve_skill(tmp_path, "missing")


def test_expected_skill_tag_reads_meta_and_formats_tag(tmp_path: Path) -> None:
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "_meta.json").write_text(
        json.dumps({"name": "demo", "version": "1.2.3"}),
        encoding="utf-8",
    )

    meta, tag = expected_skill_tag(skill_dir)

    assert meta["name"] == "demo"
    assert meta["version"] == "1.2.3"
    assert tag == "skill/demo/v1.2.3"
