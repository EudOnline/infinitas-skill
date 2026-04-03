from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.discovery.inspect import inspect_skill
from infinitas_skill.memory.contracts import MemoryRecord, MemorySearchResult


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prepare_repo(tmp_path: Path) -> Path:
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
                            "distribution_manifest_path": "catalog/distributions/consume/manifest.json",
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


class FakeMemoryProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def __init__(self, records: list[dict]):
        self._records = [
            MemoryRecord(
                memory=item["memory"],
                memory_type=item.get("memory_type", "generic"),
                score=item.get("score"),
            )
            for item in records
        ]

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        return MemorySearchResult(backend=self.backend_name, records=self._records)


def test_inspect_returns_experience_hints_as_advisory_context(tmp_path: Path):
    repo = _prepare_repo(tmp_path)
    payload = inspect_skill(
        repo,
        name="lvxiaoer/consume-infinitas-skill",
        memory_provider=FakeMemoryProvider(
            [
                {
                    "memory": "OpenClaw installs usually succeed when the release is already materialized.",
                    "memory_type": "experience",
                    "score": 0.94,
                }
            ]
        ),
        memory_scope={"user_ref": "maintainer"},
    )
    assert payload["memory_hints"]["used"] is True
    assert payload["memory_hints"]["items"][0]["memory_type"] == "experience"
    assert payload["trust_state"] == "verified"
    assert payload["trust"]["state"] == "verified"
