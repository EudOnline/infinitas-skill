from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.discovery.recommendation import recommend_skills
from infinitas_skill.memory.contracts import MemoryRecord, MemorySearchResult


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_discovery_index() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-04-03T00:00:00Z",
        "default_registry": "self",
        "sources": [
            {
                "name": "self",
                "kind": "git",
                "priority": 100,
                "trust_level": "private",
                "root": ".",
                "status": "ready",
            }
        ],
        "resolution_policy": {
            "private_registry_first": True,
            "external_requires_confirmation": True,
            "auto_install_mutable_sources": False,
        },
        "skills": [
            {
                "name": "alpha-safe",
                "qualified_name": "team/alpha-safe",
                "publisher": "team",
                "summary": "Codex helper for saturn workflows",
                "source_registry": "self",
                "source_priority": 100,
                "match_names": ["alpha-safe", "team/alpha-safe"],
                "default_install_version": "1.0.0",
                "latest_version": "1.0.0",
                "available_versions": ["1.0.0"],
                "agent_compatible": ["codex"],
                "install_requires_confirmation": False,
                "trust_level": "private",
                "trust_state": "verified",
                "tags": ["helper", "ops"],
                "verified_support": {},
                "attestation_formats": ["ssh"],
                "use_when": ["Need codex helper"],
                "avoid_when": [],
                "runtime_assumptions": ["Repo is available"],
                "maturity": "stable",
                "quality_score": 70,
                "last_verified_at": "2026-04-03T00:00:00Z",
                "capabilities": ["repo-operations"],
            },
            {
                "name": "beta-preferred",
                "qualified_name": "team/beta-preferred",
                "publisher": "team",
                "summary": "Codex helper for neptune workflows",
                "source_registry": "self",
                "source_priority": 100,
                "match_names": ["beta-preferred", "team/beta-preferred"],
                "default_install_version": "1.0.0",
                "latest_version": "1.0.0",
                "available_versions": ["1.0.0"],
                "agent_compatible": ["codex"],
                "install_requires_confirmation": False,
                "trust_level": "private",
                "trust_state": "verified",
                "tags": ["helper", "ops"],
                "verified_support": {},
                "attestation_formats": ["ssh"],
                "use_when": ["Need codex helper"],
                "avoid_when": [],
                "runtime_assumptions": ["Repo is available"],
                "maturity": "stable",
                "quality_score": 70,
                "last_verified_at": "2026-04-03T00:00:00Z",
                "capabilities": ["repo-operations"],
            },
            {
                "name": "gamma-unsafe",
                "qualified_name": "team/gamma-unsafe",
                "publisher": "team",
                "summary": "Codex helper for pluto workflows",
                "source_registry": "self",
                "source_priority": 100,
                "match_names": ["gamma-unsafe", "team/gamma-unsafe"],
                "default_install_version": "1.0.0",
                "latest_version": "1.0.0",
                "available_versions": ["1.0.0"],
                "agent_compatible": ["codex"],
                "install_requires_confirmation": False,
                "trust_level": "private",
                "trust_state": "verified",
                "tags": ["helper", "ops"],
                "verified_support": {
                    "codex": {
                        "state": "unsupported",
                        "checked_at": "2026-04-03T00:00:00Z",
                        "freshness_state": "fresh",
                    }
                },
                "attestation_formats": ["ssh"],
                "use_when": ["Need codex helper"],
                "avoid_when": [],
                "runtime_assumptions": ["Repo is available"],
                "maturity": "stable",
                "quality_score": 390,
                "last_verified_at": "2026-04-03T00:00:00Z",
                "capabilities": ["repo-operations"],
            },
        ],
    }


class FakeMemoryProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        return MemorySearchResult(
            backend=self.backend_name,
            records=[
                MemoryRecord(
                    memory="User prefers neptune workflows for codex helper choices.",
                    memory_type="user_preference",
                    score=0.96,
                ),
                MemoryRecord(
                    memory="Pluto workflow often fails due to unsupported runtime.",
                    memory_type="experience",
                    score=0.91,
                ),
            ],
        )


class FailingMemoryProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        raise RuntimeError("provider offline")


class NegativeMemoryProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        return MemorySearchResult(
            backend=self.backend_name,
            records=[
                MemoryRecord(
                    memory="Neptune workflow fails and is broken for codex helper choices.",
                    memory_type="experience",
                    score=0.99,
                )
            ],
        )


class WeightedPreferenceProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        return MemorySearchResult(
            backend=self.backend_name,
            records=[
                MemoryRecord(
                    memory="Prefer saturn workflows for codex helper choices.",
                    memory_type="user_preference",
                    score=0.94,
                    metadata={"confidence": 0.3, "ttl_seconds": 60 * 60 * 24 * 7},
                ),
                MemoryRecord(
                    memory="Prefer neptune workflows for codex helper choices.",
                    memory_type="user_preference",
                    score=0.74,
                    metadata={"confidence": 0.95, "ttl_seconds": 60 * 60 * 24 * 90},
                ),
            ],
        )


def _prepare_repo(tmp_path: Path) -> Path:
    _write_json(tmp_path / "config" / "registry-sources.json", {"registries": []})
    _write_json(tmp_path / "catalog" / "discovery-index.json", _build_discovery_index())
    return tmp_path


def test_recommendation_applies_soft_memory_boost_without_bypassing_compatibility(tmp_path: Path):
    repo = _prepare_repo(tmp_path)

    baseline = recommend_skills(
        repo,
        task="Need codex helper for workflows",
        target_agent="codex",
        limit=3,
    )
    assert baseline["results"][0]["qualified_name"] == "team/alpha-safe"

    payload = recommend_skills(
        repo,
        task="Need codex helper for workflows",
        target_agent="codex",
        limit=3,
        memory_provider=FakeMemoryProvider(),
        memory_scope={"user_ref": "maintainer"},
        memory_context_enabled=True,
    )

    assert payload["results"][0]["qualified_name"] == "team/beta-preferred"
    assert payload["results"][0]["memory_signals"]["matched_memory_count"] == 1
    assert payload["results"][0]["memory_signals"]["applied_boost"] > 0
    assert payload["results"][0]["memory_signals"]["memory_types"] == ["user_preference"]
    assert payload["explanation"]["memory_summary"] == {
        "used": True,
        "backend": "fake",
        "matched_count": 2,
        "advisory_only": True,
        "status": "matched",
    }

    incompatible = next(
        item for item in payload["results"] if item["qualified_name"] == "team/gamma-unsafe"
    )
    assert incompatible["ranking_factors"]["compatibility"] is False
    assert incompatible["memory_signals"]["applied_boost"] == 0
    assert payload["results"][0]["qualified_name"] != "team/gamma-unsafe"


def test_negative_experience_memory_does_not_add_positive_boost(tmp_path: Path):
    repo = _prepare_repo(tmp_path)
    payload = recommend_skills(
        repo,
        task="Need codex helper for workflows",
        target_agent="codex",
        limit=3,
        memory_provider=NegativeMemoryProvider(),
        memory_scope={"user_ref": "maintainer"},
        memory_context_enabled=True,
    )
    top = payload["results"][0]
    assert top["qualified_name"] == "team/alpha-safe"
    assert top["memory_signals"]["matched_memory_count"] == 0
    assert top["memory_signals"]["applied_boost"] == 0
    assert payload["explanation"]["memory_summary"]["used"] is False
    assert payload["explanation"]["memory_summary"]["matched_count"] == 1
    assert payload["explanation"]["memory_summary"]["status"] == "matched"


def test_memory_summary_surfaces_provider_failure_when_memory_enabled(tmp_path: Path):
    repo = _prepare_repo(tmp_path)
    payload = recommend_skills(
        repo,
        task="Need codex helper for workflows",
        target_agent="codex",
        limit=3,
        memory_provider=FailingMemoryProvider(),
        memory_scope={"user_ref": "maintainer"},
        memory_context_enabled=True,
    )
    summary = payload["explanation"]["memory_summary"]
    assert summary["used"] is False
    assert summary["status"] == "error"
    assert summary["matched_count"] == 0
    assert summary["backend"] == "fake"
    assert "provider offline" in summary["error"]


def test_recommendation_prefers_higher_quality_matched_memory_when_base_scores_tie(tmp_path: Path):
    repo = _prepare_repo(tmp_path)
    payload = recommend_skills(
        repo,
        task="Need codex helper for workflows",
        target_agent="codex",
        limit=3,
        memory_provider=WeightedPreferenceProvider(),
        memory_scope={"user_ref": "maintainer"},
        memory_context_enabled=True,
    )
    assert payload["results"][0]["qualified_name"] == "team/beta-preferred"
    assert payload["results"][0]["memory_signals"]["applied_boost"] > payload["results"][1][
        "memory_signals"
    ]["applied_boost"]
