from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.discovery.inspect import inspect_skill
from infinitas_skill.discovery.recommendation import recommend_skills
from infinitas_skill.memory.contracts import MemoryRecord, MemorySearchResult

ROOT = Path(__file__).resolve().parents[2]


class FixtureMemoryProvider:
    backend_name = "fixture"
    capabilities = {"read": True, "write": True}

    def __init__(self, records: list[dict]):
        self._records = [
            MemoryRecord(
                memory=item["memory"],
                memory_type=item.get("memory_type", "generic"),
                score=item.get("score"),
                metadata={
                    key: item[key]
                    for key in ("confidence", "ttl_seconds")
                    if key in item
                },
            )
            for item in records
        ]

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        return MemorySearchResult(backend=self.backend_name, records=self._records)


def _load_fixture(name: str):
    path = ROOT / "tests" / "fixtures" / "memory_eval" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_recommendation_repo(tmp_path: Path) -> Path:
    _write_json(tmp_path / "config" / "registry-sources.json", {"registries": []})
    _write_json(
        tmp_path / "catalog" / "discovery-index.json",
        {
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
        },
    )
    return tmp_path


def _build_inspect_repo(tmp_path: Path) -> Path:
    _write_json(
        tmp_path / "catalog" / "ai-index.json",
        {
            "schema_version": 1,
            "generated_at": "2026-04-03T00:00:00Z",
            "skills": [
                {
                    "name": "consume-infinitas-skill",
                    "qualified_name": "lvxiaoer/consume-infinitas-skill",
                    "publisher": "lvxiaoer",
                    "summary": "consume released skills",
                    "default_install_version": "1.0.0",
                    "latest_version": "1.0.0",
                    "versions": {
                        "1.0.0": {
                            "distribution_manifest_path": (
                                "catalog/distributions/consume/manifest.json"
                            ),
                            "attestation_path": "catalog/provenance/consume.json",
                            "attestation_signature_path": "catalog/provenance/consume.json.ssig",
                            "attestation_formats": ["ssh"],
                            "bundle_path": "catalog/distributions/consume/skill.tar.gz",
                            "bundle_sha256": "abc123",
                        }
                    },
                    "compatibility": {
                        "declared_support": ["openclaw"],
                        "verified_support": {
                            "openclaw": {"state": "native", "freshness_state": "fresh"}
                        },
                    },
                    "use_when": ["Need to install released skills"],
                    "avoid_when": ["Need release-authoring operations"],
                    "capabilities": ["search", "inspect", "install"],
                    "runtime_assumptions": ["artifact catalog is available"],
                    "maturity": "stable",
                    "quality_score": 89,
                }
            ],
        },
    )
    _write_json(
        tmp_path / "catalog" / "distributions.json",
        {
            "schema_version": 1,
            "skills": [
                {
                    "qualified_name": "lvxiaoer/consume-infinitas-skill",
                    "name": "consume-infinitas-skill",
                    "version": "1.0.0",
                    "manifest_path": "catalog/distributions/consume/manifest.json",
                    "attestation_path": "catalog/provenance/consume.json",
                    "attestation_signature_path": "catalog/provenance/consume.json.ssig",
                    "bundle_path": "catalog/distributions/consume/skill.tar.gz",
                    "bundle_sha256": "abc123",
                    "source_type": "distribution-manifest",
                    "dependencies": {
                        "root": {"name": "consume-infinitas-skill", "source_type": "release"},
                        "steps": [{"registry": "self"}],
                        "registries_consulted": ["self"],
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / "catalog" / "distributions" / "consume" / "manifest.json",
        {
            "dependencies": {
                "root": {"name": "consume-infinitas-skill", "source_type": "release"},
                "steps": [{"registry": "self"}],
                "registries_consulted": ["self"],
            },
            "bundle": {"size": 1024, "file_count": 3},
            "attestation_bundle": {
                "signature_path": "catalog/provenance/consume.json.ssig",
                "provenance_path": "catalog/provenance/consume.json",
                "signer_identity": "test-signer",
            },
        },
    )
    _write_json(
        tmp_path / "catalog" / "provenance" / "consume.json",
        {
            "attestation": {
                "format": "ssh",
                "policy_mode": "enforce",
                "require_verified_attestation_for_distribution": True,
            }
        },
    )
    return tmp_path


def test_recommendation_memory_evaluation_matrix(tmp_path: Path):
    repo = _build_recommendation_repo(tmp_path / "recommend")
    cases = _load_fixture("recommendation_cases.json")

    for case in cases:
        payload = recommend_skills(
            repo,
            task=case["task"],
            target_agent=case["target_agent"],
            limit=3,
            memory_provider=FixtureMemoryProvider(case["memory_records"]),
            memory_scope=case.get("memory_scope"),
            memory_context_enabled=case["memory_context_enabled"],
        )
        assert payload["results"][0]["qualified_name"] == case["expected_winner"], case["name"]
        assert payload["explanation"]["memory_summary"]["used"] is case["expected_memory_used"]
        curation_summary = case.get("expected_curation_summary")
        if curation_summary:
            assert (
                payload["explanation"]["memory_summary"]["curation_summary"] == curation_summary
            ), case["name"]
        forbidden = case.get("forbidden_top_result")
        if forbidden:
            assert payload["results"][0]["qualified_name"] != forbidden


def test_inspect_memory_evaluation_matrix(tmp_path: Path):
    repo = _build_inspect_repo(tmp_path / "inspect")
    cases = _load_fixture("inspect_cases.json")

    for case in cases:
        payload = inspect_skill(
            repo,
            name="lvxiaoer/consume-infinitas-skill",
            memory_provider=FixtureMemoryProvider(case["memory_records"]),
            memory_scope=case.get("memory_scope"),
            memory_context_enabled=case["memory_context_enabled"],
        )
        assert payload["trust_state"] == case["expected_trust_state"], case["name"]
        assert payload["trust"]["state"] == case["expected_trust_state"], case["name"]
        assert (
            payload["memory_hints"]["items"][0]["memory_type"]
            == case["expected_first_memory_type"]
        )
        curation_summary = case.get("expected_curation_summary")
        if curation_summary:
            assert payload["memory_hints"]["curation_summary"] == curation_summary, case["name"]
