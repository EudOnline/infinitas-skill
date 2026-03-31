from __future__ import annotations

from pathlib import Path

from infinitas_skill.install.source_resolution import candidate_from_skill_dir

ROOT = Path(__file__).resolve().parents[3]


def test_candidate_from_skill_dir_prefers_explicit_source_registry() -> None:
    candidate = candidate_from_skill_dir(
        ROOT / "templates" / "basic-skill",
        source_registry="external-fixture",
        source_info={"registry_name": "self", "registry_priority": 7},
    )

    assert candidate["name"] == "basic-skill"
    assert candidate["version"] == "0.1.0"
    assert candidate["registry_name"] == "external-fixture"
    assert candidate["source_type"] == "working-tree"
