from __future__ import annotations

import json
from pathlib import Path

import pytest

from infinitas_skill.install.distribution import distribution_rel_dir
from infinitas_skill.install.distribution_core import DistributionError
from infinitas_skill.install.install_manifest import (
    InstallManifestError,
    normalize_install_manifest,
)
from infinitas_skill.install.source_resolution import DependencyError, normalize_meta_dependencies
from infinitas_skill.skills.canonical import (
    CanonicalSkillError,
    load_skill_source,
    validate_canonical_payload,
)


def test_missing_schema_version_is_rejected() -> None:
    payload = {
        "name": "strict-skill",
        "summary": "Strict",
        "description": "Strict schema fixture",
        "instructions_body": "instructions.md",
        "tool_intents": {"required": [], "optional": []},
        "verification": {"required_runtimes": [], "smoke_prompts": []},
    }

    assert "missing required schema_version" in validate_canonical_payload(payload)


def test_legacy_skill_layout_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "_meta.json").write_text(
        json.dumps({"schema_version": 1, "name": "old-skill"}), encoding="utf-8"
    )
    (tmp_path / "SKILL.md").write_text("# Old skill\n", encoding="utf-8")

    with pytest.raises(CanonicalSkillError, match="unsupported skill source layout"):
        load_skill_source(tmp_path)


def test_required_platforms_alias_is_rejected() -> None:
    payload = {
        "schema_version": 1,
        "name": "strict-skill",
        "summary": "Strict",
        "description": "Strict schema fixture",
        "instructions_body": "instructions.md",
        "tool_intents": {"required": [], "optional": []},
        "verification": {"required_platforms": ["codex"], "smoke_prompts": []},
    }

    assert "verification.required_runtimes must be an array of strings" in (
        validate_canonical_payload(payload)
    )


def test_distribution_path_requires_publisher() -> None:
    with pytest.raises(DistributionError, match="publisher must be a non-empty string"):
        distribution_rel_dir("strict-skill", "1.0.0", publisher="")


def test_install_manifest_requires_schema_version() -> None:
    with pytest.raises(InstallManifestError, match="missing required schema_version"):
        normalize_install_manifest({"skills": {}, "history": {}})


def test_install_manifest_rejects_legacy_distribution_paths() -> None:
    with pytest.raises(InstallManifestError, match="legacy distribution paths"):
        normalize_install_manifest(
            {
                "schema_version": 1,
                "skills": {
                    "old": {
                        "name": "old",
                        "source_distribution_manifest": (
                            "catalog/distributions/_legacy/old/1.0.0/manifest.json"
                        ),
                    }
                },
                "history": {},
            }
        )


def test_dependency_refs_require_object_format() -> None:
    with pytest.raises(DependencyError, match="depends_on entries must use object format"):
        normalize_meta_dependencies(
            {"name": "strict-skill", "publisher": "owner", "depends_on": ["other@1.0.0"]}
        )
