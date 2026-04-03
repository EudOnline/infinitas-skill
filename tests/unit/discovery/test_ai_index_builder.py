from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.discovery.ai_index_builder import build_ai_index


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_build_ai_index_chooses_latest_version_and_preserves_trust_metadata(tmp_path: Path) -> None:
    root = tmp_path
    _write_json(
        root / "skills" / "demo" / "_meta.json",
        {
            "publisher": "team",
            "tags": ["ops"],
            "use_when": ["Need repo operations"],
            "avoid_when": [],
            "runtime_assumptions": ["Repo available"],
            "entrypoints": {"skill_md": "SKILL.md"},
            "requires": {"tools": [], "env": []},
        },
    )

    payload = build_ai_index(
        root=root,
        catalog_entries=[
            {
                "name": "demo",
                "qualified_name": "team/demo",
                "summary": "demo skill",
                "path": "skills/demo",
                "verified_support": {
                    "codex": {
                        "state": "native",
                        "checked_at": "2026-04-03T00:00:00Z",
                        "freshness_state": "fresh",
                    }
                },
                "source_registry": "self",
            }
        ],
        distribution_entries=[
            {
                "qualified_name": "team/demo",
                "name": "demo",
                "version": "1.0.0",
                "manifest_path": "catalog/distributions/demo/1.0.0/manifest.json",
                "bundle_path": "catalog/distributions/demo/1.0.0/skill.tar.gz",
                "bundle_sha256": "abc",
                "attestation_path": "catalog/provenance/demo-1.0.0.json",
                "generated_at": "2026-04-02T00:00:00Z",
            },
            {
                "qualified_name": "team/demo",
                "name": "demo",
                "version": "1.2.0",
                "manifest_path": "catalog/distributions/demo/1.2.0/manifest.json",
                "bundle_path": "catalog/distributions/demo/1.2.0/skill.tar.gz",
                "bundle_sha256": "def",
                "attestation_path": "catalog/provenance/demo-1.2.0.json",
                "attestation_signature_path": "catalog/provenance/demo-1.2.0.json.ssig",
                "generated_at": "2026-04-03T00:00:00Z",
            },
        ],
    )

    skill = payload["skills"][0]
    assert skill["latest_version"] == "1.2.0"
    assert skill["default_install_version"] == "1.2.0"
    assert skill["trust_state"] == "verified"
    assert skill["versions"]["1.2.0"]["trust_state"] == "verified"
    assert skill["versions"]["1.2.0"]["distribution_manifest_path"].endswith("1.2.0/manifest.json")

