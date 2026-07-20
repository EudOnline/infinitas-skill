from __future__ import annotations

from pathlib import Path

from infinitas_skill.registry.catalog_entries import stable_catalog_identity


def test_local_only_catalog_identity_uses_configured_origin_url(tmp_path: Path) -> None:
    registry = {
        "kind": "git",
        "local_path": ".",
        "url": "https://github.com/EudOnline/infinitas-skill.git",
        "update_policy": {"mode": "local-only"},
    }
    identity = {
        "registry_update_mode": "local-only",
        "registry_commit": "abc123",
        "registry_tag": "v0.1.0",
        "registry_branch": "main",
        "registry_origin_url": "git@github.com:EudOnline/infinitas-skill.git",
    }

    stable = stable_catalog_identity(tmp_path, registry, identity)

    assert stable["registry_commit"] is None
    assert stable["registry_tag"] is None
    assert stable["registry_branch"] is None
    assert stable["registry_origin_url"] == registry["url"]
