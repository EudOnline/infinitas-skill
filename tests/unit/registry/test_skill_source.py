from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from infinitas_skill.registry.skill_source import (
    SkillSourceError,
    build_skill_source_bundle,
    stage_skill_source,
)


def _write_plain_skill(root: Path, *, name: str = "adapt") -> Path:
    source = root / name
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: Adapt an interface for another context.\n"
        "---\n\n"
        "# Adapt\n\n"
        "Inspect the source and target contexts before changing the design.\n",
        encoding="utf-8",
    )
    return source


def test_stages_plain_agent_skill_without_mutating_source(tmp_path: Path) -> None:
    source = _write_plain_skill(tmp_path / "source")
    staged_root = tmp_path / "staged"

    result = stage_skill_source(
        source,
        staged_root,
        publisher="tdcasual",
        version="1.2.0",
    )

    assert result.slug == "adapt"
    assert result.qualified_name == "tdcasual/adapt"
    assert result.generated_files == ("CHANGELOG.md", "_meta.json", "tests/smoke.md")
    assert not (source / "_meta.json").exists()
    assert result.skill_dir == staged_root / "active" / "adapt"
    metadata = json.loads((result.skill_dir / "_meta.json").read_text(encoding="utf-8"))
    assert metadata["version"] == "1.2.0"
    assert metadata["publisher"] == "tdcasual"
    assert metadata["qualified_name"] == "tdcasual/adapt"
    assert metadata["review_state"] == "draft"
    assert metadata["risk_level"] == "medium"


def test_existing_metadata_is_preserved_but_hosted_identity_is_authoritative(
    tmp_path: Path,
) -> None:
    source = _write_plain_skill(tmp_path / "source")
    (source / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (source / "tests").mkdir()
    (source / "tests" / "smoke.md").write_text("# Smoke\n", encoding="utf-8")
    (source / "_meta.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "adapt",
                "publisher": "someone-else",
                "qualified_name": "someone-else/adapt",
                "version": "0.1.0",
                "status": "active",
                "summary": "Existing summary",
                "owner": "someone-else",
                "review_state": "approved",
                "risk_level": "low",
                "tags": ["responsive"],
                "distribution": {"installable": True, "channel": "git"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = stage_skill_source(
        source,
        tmp_path / "staged",
        publisher="tdcasual",
        version="2.0.0",
    )

    metadata = json.loads((result.skill_dir / "_meta.json").read_text(encoding="utf-8"))
    assert metadata["summary"] == "Existing summary"
    assert metadata["tags"] == ["responsive"]
    assert metadata["publisher"] == "tdcasual"
    assert metadata["qualified_name"] == "tdcasual/adapt"
    assert metadata["version"] == "2.0.0"
    assert metadata["owner"] == "tdcasual"
    assert metadata["distribution"] == {"installable": True, "channel": "hosted"}
    assert result.generated_files == ("_meta.json",)


def test_builds_deterministic_validated_bundle(tmp_path: Path) -> None:
    source = _write_plain_skill(tmp_path / "source")
    result = stage_skill_source(
        source,
        tmp_path / "staged",
        publisher="tdcasual",
        version="1.0.0",
    )
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"

    build_skill_source_bundle(result, first, repo_root=Path.cwd())
    build_skill_source_bundle(result, second, repo_root=Path.cwd())

    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, "r:gz") as archive:
        names = set(archive.getnames())
    assert "adapt/SKILL.md" in names
    assert "adapt/_meta.json" in names
    assert "adapt/tests/smoke.md" in names


def test_bundle_permissions_are_stable_across_umask(tmp_path: Path) -> None:
    source = _write_plain_skill(tmp_path / "source")
    result = stage_skill_source(
        source,
        tmp_path / "staged",
        publisher="tdcasual",
        version="1.0.0",
    )
    generated = result.skill_dir / "generated.sh"
    generated.write_text("#!/bin/sh\n", encoding="utf-8")
    generated.chmod(0o775)

    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    build_skill_source_bundle(result, first, repo_root=Path.cwd())

    for path in result.skill_dir.rglob("*"):
        if path.is_file() and path != generated:
            path.chmod(0o644)
    generated.chmod(0o755)
    build_skill_source_bundle(result, second, repo_root=Path.cwd())

    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, "r:gz") as archive:
        modes = {member.name: member.mode for member in archive.getmembers()}
    assert modes["adapt/SKILL.md"] == 0o644
    assert modes["adapt/_meta.json"] == 0o644
    assert modes["adapt/generated.sh"] == 0o755


def test_rejects_symlinks_before_staging(tmp_path: Path) -> None:
    source = _write_plain_skill(tmp_path / "source")
    (source / "linked.txt").symlink_to(source / "SKILL.md")

    with pytest.raises(SkillSourceError, match="symbolic links"):
        stage_skill_source(
            source,
            tmp_path / "staged",
            publisher="tdcasual",
            version="1.0.0",
        )
