from __future__ import annotations

from infinitas_skill.discovery.inspect_view import build_inspect_payload


def test_build_inspect_payload_keeps_trust_fields_authoritative_when_memory_is_present():
    payload = build_inspect_payload(
        skill_entry={
            "name": "consume-infinitas-skill",
            "qualified_name": "lvxiaoer/consume-infinitas-skill",
            "publisher": "lvxiaoer",
            "latest_version": "1.0.0",
            "compatibility": {
                "declared_support": ["openclaw"],
                "verified_support": {"openclaw": {"state": "native", "freshness_state": "fresh"}},
            },
            "use_when": ["Need to install released skills"],
            "avoid_when": ["Need release-authoring operations"],
            "capabilities": ["search", "inspect", "install"],
            "runtime_assumptions": ["artifact catalog is available"],
            "maturity": "stable",
            "quality_score": 89,
        },
        resolved_version="1.0.0",
        trust_state="verified",
        verified_support={"openclaw": {"state": "native", "freshness_state": "fresh"}},
        dependency_view={"summary": {"root_name": "consume-infinitas-skill"}},
        provenance_view={
            "attestation_path": "catalog/provenance/consume.json",
            "release_provenance_path": "catalog/provenance/consume.json",
            "attestation_signature_path": "catalog/provenance/consume.json.ssig",
            "attestation_formats": ["ssh"],
            "required_attestation_formats": ["ssh"],
            "signer_identity": "test-signer",
            "policy": {"require_verified_attestation_for_distribution": True},
        },
        distribution_view={
            "manifest_path": "catalog/distributions/consume/manifest.json",
            "bundle_path": "catalog/distributions/consume/skill.tar.gz",
            "bundle_sha256": "abc123",
            "source_type": "distribution-manifest",
            "bundle_size": 1024,
            "bundle_file_count": 3,
        },
        trust_view={
            "state": "verified",
            "manifest_present": True,
            "attestation_present": True,
            "signature_present": True,
            "required_attestation_formats": ["ssh"],
        },
        memory_hints={
            "used": True,
            "backend": "fake",
            "matched_count": 1,
            "status": "matched",
            "advisory_only": True,
            "items": [
                {
                    "memory_type": "experience",
                    "memory": (
                        "OpenClaw installs usually succeed when the release "
                        "is already materialized."
                    ),
                    "score": 0.94,
                }
            ],
        },
    )

    assert payload["trust_state"] == "verified"
    assert payload["trust"]["state"] == "verified"
    assert payload["memory_hints"]["used"] is True
    assert payload["memory_hints"]["items"][0]["memory_type"] == "experience"
