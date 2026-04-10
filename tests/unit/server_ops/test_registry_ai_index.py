from __future__ import annotations

from server.modules.registry.service import _build_ai_index_from_entries


def test_registry_ai_index_uses_canonical_openclaw_runtime_targets() -> None:
    payload = _build_ai_index_from_entries(
        [
            {
                "name": "demo-runtime-skill",
                "publisher": "team",
                "qualified_name": "team/demo-runtime-skill",
                "version": "1.0.0",
                "summary": "demo",
                "manifest_path": "catalog/distributions/demo-runtime-skill/1.0.0/manifest.json",
                "bundle_path": "catalog/distributions/demo-runtime-skill/1.0.0/skill.tar.gz",
                "bundle_sha256": "sha-demo",
                "attestation_path": "catalog/provenance/demo-runtime-skill-1.0.0.json",
                "attestation_signature_path": (
                    "catalog/provenance/demo-runtime-skill-1.0.0.json.ssig"
                ),
                "published_at": "2026-04-08T00:00:00Z",
                "display_name": "Demo Runtime Skill",
                "audience_type": "public",
                "listing_mode": "listed",
                "release_id": 1,
                "exposure_id": 1,
            }
        ]
    )

    skill = payload["skills"][0]
    interop = (skill.get("interop") or {}).get("openclaw") or {}

    assert interop.get("runtime_targets") == [
        "skills",
        ".agents/skills",
        "~/.agents/skills",
        "~/.openclaw/skills",
    ]
