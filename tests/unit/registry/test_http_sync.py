from __future__ import annotations

import json
from pathlib import Path

import pytest

from infinitas_skill.registry import sync


def test_http_registry_sync_caches_catalogs_and_records_refresh_state(
    monkeypatch, tmp_path: Path
) -> None:
    registry = {
        "name": "hosted",
        "kind": "http",
        "base_url": "https://registry.example/api/v1/registry",
        "auth": {"mode": "token", "env": "HOSTED_TOKEN"},
    }
    payloads = {
        "ai-index.json": {"schema_version": 1, "skills": []},
        "distributions.json": {"schema_version": 1, "skills": []},
        "compatibility.json": {"schema_version": 1, "skills": []},
    }
    monkeypatch.setattr(sync, "_load_registry", lambda root, name: registry)
    monkeypatch.setattr(
        sync,
        "fetch_json",
        lambda base_url, path, token_env=None: payloads[path],
    )

    result = sync.sync_registry_source(root=tmp_path, name="hosted")

    assert result["mode"] == "remote-only"
    assert len(result["digest"]) == 64
    cache_root = tmp_path / ".cache" / "registries" / "hosted"
    assert json.loads((cache_root / "catalog" / "ai-index.json").read_text())["skills"] == []
    assert json.loads((cache_root / "catalog" / "distributions.json").read_text())["skills"] == []
    state = json.loads((tmp_path / ".cache" / "registries" / "_state" / "hosted.json").read_text())
    assert state["kind"] == "http"
    assert state["source_commit"] == result["digest"]
    assert state["cache_path"] == str(cache_root.resolve())


def test_http_registry_sync_preserves_previous_cache_when_catalog_fetch_fails(
    monkeypatch, tmp_path: Path
) -> None:
    registry = {
        "name": "hosted",
        "kind": "http",
        "base_url": "https://registry.example/api/v1/registry",
    }
    cache_root = tmp_path / ".cache" / "registries" / "hosted"
    previous_catalog = cache_root / "catalog" / "ai-index.json"
    previous_catalog.parent.mkdir(parents=True)
    previous_catalog.write_text('{"generation":"previous"}', encoding="utf-8")
    monkeypatch.setattr(sync, "_load_registry", lambda root, name: registry)

    def fail_on_distributions(base_url: str, path: str, token_env=None) -> dict:
        if path == "distributions.json":
            raise sync.HostedRegistryError("temporary failure")
        return {"schema_version": 1, "skills": []}

    monkeypatch.setattr(sync, "fetch_json", fail_on_distributions)

    with pytest.raises(sync.RegistrySyncError, match="temporary failure"):
        sync.sync_registry_source(root=tmp_path, name="hosted")

    assert json.loads(previous_catalog.read_text()) == {"generation": "previous"}


def test_http_registry_sync_rolls_back_cache_when_refresh_state_write_fails(
    monkeypatch, tmp_path: Path
) -> None:
    registry = {
        "name": "hosted",
        "kind": "http",
        "base_url": "https://registry.example/api/v1/registry",
    }
    cache_root = tmp_path / ".cache" / "registries" / "hosted"
    previous_catalog = cache_root / "catalog" / "ai-index.json"
    previous_catalog.parent.mkdir(parents=True)
    previous_catalog.write_text('{"generation":"previous"}', encoding="utf-8")
    monkeypatch.setattr(sync, "_load_registry", lambda root, name: registry)
    monkeypatch.setattr(
        sync,
        "fetch_json",
        lambda base_url, path, token_env=None: {"generation": "next", "skills": []},
    )
    monkeypatch.setattr(
        sync,
        "write_refresh_state",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("state write failed")),
    )

    with pytest.raises(OSError, match="state write failed"):
        sync.sync_registry_source(root=tmp_path, name="hosted")

    assert json.loads(previous_catalog.read_text()) == {"generation": "previous"}
    assert not list(cache_root.parent.glob(".hosted.sync-*"))
    assert not list(cache_root.parent.glob(".hosted.previous-*"))


def test_http_registry_sync_requires_force_to_replace_non_directory_cache(
    monkeypatch, tmp_path: Path
) -> None:
    registry = {
        "name": "hosted",
        "kind": "http",
        "base_url": "https://registry.example/api/v1/registry",
    }
    cache_root = tmp_path / ".cache" / "registries" / "hosted"
    cache_root.parent.mkdir(parents=True)
    cache_root.write_text("unexpected file", encoding="utf-8")
    monkeypatch.setattr(sync, "_load_registry", lambda root, name: registry)
    monkeypatch.setattr(
        sync,
        "fetch_json",
        lambda base_url, path, token_env=None: {"schema_version": 1, "skills": []},
    )

    with pytest.raises(sync.RegistrySyncError, match="not a directory"):
        sync.sync_registry_source(root=tmp_path, name="hosted")

    assert cache_root.read_text() == "unexpected file"
    result = sync.sync_registry_source(root=tmp_path, name="hosted", force=True)
    assert result["mode"] == "remote-only"
    assert (cache_root / "catalog" / "ai-index.json").is_file()
