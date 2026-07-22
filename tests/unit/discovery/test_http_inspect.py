from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.discovery import inspect as inspect_module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_inspect_resolves_hosted_skill_from_discovery_index(monkeypatch, tmp_path: Path) -> None:
    qualified_name = "team/hosted-skill"
    manifest_path = "skills/team/hosted-skill/1.0.0/manifest.json"
    provenance_path = "provenance/team--hosted-skill-1.0.0.json"
    signature_path = provenance_path + ".ssig"
    _write_json(
        tmp_path / "catalog" / "ai-index.json",
        {"skills": []},
    )
    _write_json(
        tmp_path / "catalog" / "discovery-index.json",
        {
            "skills": [
                {
                    "name": "hosted-skill",
                    "qualified_name": qualified_name,
                    "publisher": "team",
                    "source_registry": "hosted",
                    "latest_version": "1.0.0",
                    "versions": {
                        "1.0.0": {
                            "manifest_path": manifest_path,
                            "bundle_path": "skills/team/hosted-skill/1.0.0/skill.tar.gz",
                            "bundle_sha256": "abc123",
                            "attestation_path": provenance_path,
                            "attestation_signature_path": signature_path,
                            "attestation_formats": ["ssh"],
                        }
                    },
                    "runtime": {
                        "platform": "openclaw",
                        "workspace_scope": "workspace",
                        "install_targets": {"workspace": ["skills"]},
                        "readiness": {"ready": True, "status": "ready"},
                    },
                }
            ]
        },
    )
    registry = {
        "name": "hosted",
        "kind": "http",
        "base_url": "https://registry.example/api/v1/registry",
        "auth": {"mode": "token", "env": "HOSTED_TOKEN"},
    }
    responses = {
        "distributions.json": {
            "skills": [
                {
                    "qualified_name": qualified_name,
                    "version": "1.0.0",
                    "manifest_path": manifest_path,
                    "bundle_path": "skills/team/hosted-skill/1.0.0/skill.tar.gz",
                    "bundle_sha256": "abc123",
                    "attestation_path": provenance_path,
                    "attestation_signature_path": signature_path,
                }
            ]
        },
        manifest_path: {
            "bundle": {"size": 100, "file_count": 3},
            "attestation_bundle": {
                "provenance_path": provenance_path,
                "signature_path": signature_path,
                "signer_identity": "hosted-signer",
            },
        },
        provenance_path: {
            "attestation": {
                "format": "ssh",
                "require_verified_attestation_for_distribution": True,
            }
        },
    }
    monkeypatch.setattr(
        inspect_module,
        "load_registry_config",
        lambda root: {"default_registry": "hosted", "registries": [registry]},
    )
    monkeypatch.setattr(
        inspect_module,
        "fetch_json",
        lambda base_url, path, token_env=None: responses[path],
    )

    result = inspect_module.inspect_skill(tmp_path, qualified_name)

    assert result["qualified_name"] == qualified_name
    assert result["version"] == "1.0.0"
    assert result["trust_state"] == "verified"
    assert result["distribution"]["manifest_path"] == manifest_path
    assert result["provenance"]["signer_identity"] == "hosted-signer"
