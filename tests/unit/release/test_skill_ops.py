from __future__ import annotations

import json
import shutil
from pathlib import Path

from infinitas_skill.release.skill_ops import bump_skill_version, scaffold_skill

ROOT = Path(__file__).resolve().parents[3]


def test_scaffold_skill_sets_current_identity_schema(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "templates", tmp_path / "templates")

    payload = scaffold_skill(
        root=tmp_path,
        requested_name="lvxiaoer/demo-skill",
        template="basic",
        target_root="skills/incubating",
    )

    skill_dir = Path(payload["target_dir"])
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    assert meta["schema_version"] == 1
    assert meta["publisher"] == "lvxiaoer"
    assert meta["qualified_name"] == "lvxiaoer/demo-skill"
    assert "name: demo-skill" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_bump_skill_version_updates_meta_and_changelog(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "templates" / "basic-skill", tmp_path / "demo-skill")

    payload = bump_skill_version(tmp_path / "demo-skill", bump_kind="minor", notes=["Clean API"])

    assert payload["from_version"] == "0.1.0"
    assert payload["to_version"] == "0.2.0"
    assert "## 0.2.0" in (tmp_path / "demo-skill" / "CHANGELOG.md").read_text(encoding="utf-8")
