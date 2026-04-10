from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.discovery.ai_index import validate_ai_index_payload
from infinitas_skill.discovery.ai_index_builder import build_ai_index
from infinitas_skill.discovery.index import build_discovery_index
from infinitas_skill.discovery.inspect import inspect_skill
from infinitas_skill.discovery.recommendation import recommend_skills


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_runtime_fixture_index(root: Path) -> dict:
    _write_json(
        root / "skills" / "demo-runtime-skill" / "_meta.json",
        {
            "name": "demo-runtime-skill",
            "version": "1.3.0",
            "publisher": "team",
            "summary": "OpenClaw runtime fixture",
            "tags": ["runtime", "ops"],
            "use_when": ["Need OpenClaw runtime checks"],
            "avoid_when": [],
            "runtime_assumptions": ["workspace write access available"],
            "entrypoints": {"skill_md": "SKILL.md"},
            "requires": {
                "tools": ["shell"],
                "env": ["OPENAI_API_KEY"],
                "bins": ["git"],
            },
            "openclaw_runtime": {
                "workspace_scope": "workspace",
                "background_tasks": {"required": True},
                "subagents": {"required": True},
            },
            "metadata": {
                "openclaw": {
                    "requires": {
                        "bins": ["git"],
                        "env": ["OPENAI_API_KEY"],
                        "config": ["memory.store.enabled"],
                    }
                }
            },
        },
    )

    payload = build_ai_index(
        root=root,
        catalog_entries=[
            {
                "name": "demo-runtime-skill",
                "qualified_name": "team/demo-runtime-skill",
                "summary": "OpenClaw runtime fixture",
                "path": "skills/demo-runtime-skill",
                "agent_compatible": ["codex"],
                "verified_support": {
                    "openclaw": {
                        "state": "native",
                        "checked_at": "2026-04-07T00:00:00Z",
                        "freshness_state": "fresh",
                    }
                },
                "source_registry": "self",
            }
        ],
        distribution_entries=[
            {
                "qualified_name": "team/demo-runtime-skill",
                "name": "demo-runtime-skill",
                "version": "1.3.0",
                "manifest_path": "catalog/distributions/demo-runtime-skill/1.3.0/manifest.json",
                "bundle_path": "catalog/distributions/demo-runtime-skill/1.3.0/skill.tar.gz",
                "bundle_sha256": "demo-runtime-skill-sha",
                "attestation_path": "catalog/provenance/demo-runtime-skill-1.3.0.json",
                "attestation_signature_path": (
                    "catalog/provenance/demo-runtime-skill-1.3.0.json.ssig"
                ),
                "generated_at": "2026-04-07T01:00:00Z",
            }
        ],
    )
    return payload


def test_ai_index_and_discovery_emit_openclaw_runtime_contract(tmp_path: Path) -> None:
    root = tmp_path
    payload = _build_runtime_fixture_index(root)

    errors = validate_ai_index_payload(payload)
    assert not errors, errors

    skill = payload["skills"][0]
    runtime = skill.get("runtime")
    assert isinstance(runtime, dict)
    assert runtime.get("platform") == "openclaw"
    assert runtime.get("skill_precedence", [])[:4] == [
        "skills",
        ".agents/skills",
        "~/.agents/skills",
        "~/.openclaw/skills",
    ]
    assert (skill.get("interop") or {}).get("openclaw", {}).get("runtime_targets") == [
        "skills",
        ".agents/skills",
        "~/.agents/skills",
        "~/.openclaw/skills",
    ]
    assert runtime.get("install_targets", {}).get("workspace") == ["skills", ".agents/skills"]
    assert runtime.get("requires_detail", {}).get("bins") == ["git"]
    assert runtime.get("requires_detail", {}).get("config") == ["memory.store.enabled"]
    assert runtime.get("background_tasks", {}).get("required") is True
    assert runtime.get("subagents", {}).get("required") is True
    assert isinstance(runtime.get("readiness", {}).get("status"), str)
    assert runtime.get("legacy_compatibility", {}).get("agent_compatible_deprecated") is True

    discovery_payload = build_discovery_index(
        root=root,
        local_ai_index=payload,
        registry_config={
            "default_registry": "self",
            "registries": [
                {
                    "name": "self",
                    "kind": "git",
                    "enabled": True,
                    "priority": 100,
                    "trust": "private",
                    "local_path": ".",
                }
            ],
        },
    )

    discovery_skill = discovery_payload["skills"][0]
    assert discovery_skill.get("runtime", {}).get("platform") == "openclaw"
    assert discovery_skill.get("runtime_readiness")
    assert discovery_skill.get("workspace_targets") == ["skills", ".agents/skills"]


def test_inspect_and_recommendation_surface_runtime_readiness(tmp_path: Path) -> None:
    root = tmp_path
    ai_index = _build_runtime_fixture_index(root)
    _write_json(root / "catalog" / "ai-index.json", ai_index)
    _write_json(
        root / "catalog" / "distributions.json",
        {
            "schema_version": 1,
            "skills": [
                {
                    "qualified_name": "team/demo-runtime-skill",
                    "name": "demo-runtime-skill",
                    "version": "1.3.0",
                    "manifest_path": "catalog/distributions/demo-runtime-skill/1.3.0/manifest.json",
                    "attestation_path": "catalog/provenance/demo-runtime-skill-1.3.0.json",
                    "attestation_signature_path": (
                        "catalog/provenance/demo-runtime-skill-1.3.0.json.ssig"
                    ),
                    "bundle_path": "catalog/distributions/demo-runtime-skill/1.3.0/skill.tar.gz",
                    "bundle_sha256": "demo-runtime-skill-sha",
                    "source_type": "distribution-manifest",
                    "dependencies": {
                        "root": {"name": "demo-runtime-skill", "source_type": "release"},
                        "steps": [{"registry": "self"}],
                        "registries_consulted": ["self"],
                    },
                }
            ],
        },
    )
    _write_json(
        root / "catalog" / "distributions" / "demo-runtime-skill" / "1.3.0" / "manifest.json",
        {
            "dependencies": {
                "root": {"name": "demo-runtime-skill", "source_type": "release"},
                "steps": [{"registry": "self"}],
                "registries_consulted": ["self"],
            },
            "bundle": {"size": 256, "file_count": 2},
            "attestation_bundle": {
                "signature_path": "catalog/provenance/demo-runtime-skill-1.3.0.json.ssig",
                "provenance_path": "catalog/provenance/demo-runtime-skill-1.3.0.json",
                "signer_identity": "demo-signer",
            },
        },
    )
    _write_json(
        root / "catalog" / "provenance" / "demo-runtime-skill-1.3.0.json",
        {
            "attestation": {
                "format": "ssh",
                "policy_mode": "enforce",
                "require_verified_attestation_for_distribution": True,
            }
        },
    )

    discovery_payload = build_discovery_index(
        root=root,
        local_ai_index=ai_index,
        registry_config={
            "default_registry": "self",
            "registries": [
                {
                    "name": "self",
                    "kind": "git",
                    "enabled": True,
                    "priority": 100,
                    "trust": "private",
                    "local_path": ".",
                }
            ],
        },
    )
    _write_json(root / "catalog" / "discovery-index.json", discovery_payload)
    _write_json(
        root / "config" / "registry-sources.json", {"default_registry": "self", "registries": []}
    )

    inspect_payload = inspect_skill(root, "team/demo-runtime-skill")
    assert inspect_payload.get("runtime", {}).get("platform") == "openclaw"
    assert inspect_payload.get("runtime_readiness")
    assert inspect_payload.get("workspace_fit", {}).get("targets") == ["skills", ".agents/skills"]

    recommendation_payload = recommend_skills(
        root,
        task="install into openclaw workspace",
        target_agent="openclaw",
        limit=1,
    )
    assert recommendation_payload["results"], recommendation_payload
    first = recommendation_payload["results"][0]
    assert first.get("runtime", {}).get("platform") == "openclaw"
    assert first.get("runtime_readiness")
    assert "workspace_targets" in first
