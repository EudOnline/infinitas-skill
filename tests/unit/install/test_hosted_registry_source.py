from __future__ import annotations

from pathlib import Path

import pytest

from infinitas_skill.install.registry_sources import (
    find_registry,
    registry_identity,
    resolve_registry_root,
    validate_registry_config,
)

ROOT = Path(__file__).resolve().parents[3]


def _base_config() -> dict:
    return {
        "$schema": "../schemas/registry-sources.schema.json",
        "default_registry": "hosted",
        "registries": [
            {
                "name": "hosted",
                "kind": "http",
                "base_url": "https://skills.example.com/registry",
                "enabled": True,
                "priority": 100,
                "trust": "private",
                "auth": {"mode": "token", "env": "INFINITAS_REGISTRY_TOKEN"},
            }
        ],
    }


def _errors(cfg: dict) -> list[str]:
    return validate_registry_config(ROOT, cfg)


def test_valid_http_registry_config() -> None:
    assert _errors(_base_config()) == []


def test_http_registry_requires_base_url() -> None:
    cfg = _base_config()
    cfg["registries"][0].pop("base_url")
    errors = _errors(cfg)
    assert errors and any("http registry 'hosted' missing non-empty base_url" in e for e in errors)


@pytest.mark.parametrize("trust", ["private", "trusted", "public"])
def test_http_registry_rejects_insecure_base_url_for_trusted_tiers(trust: str) -> None:
    cfg = _base_config()
    cfg["registries"][0]["trust"] = trust
    cfg["registries"][0]["base_url"] = "http://skills.example.com/registry"
    errors = _errors(cfg)
    assert errors and any(
        f"registry 'hosted' with trust '{trust}' must use an https base_url" in e for e in errors
    )


def test_http_registry_rejects_invalid_auth_modes() -> None:
    cfg = _base_config()
    cfg["registries"][0]["auth"] = {"mode": "cookie"}
    errors = _errors(cfg)
    assert errors and any(
        "registry 'hosted' auth.mode must be one of ['none', 'token']" in e for e in errors
    )


def test_http_registry_identity_resolves_without_local_clone() -> None:
    cfg = _base_config()
    assert _errors(cfg) == []
    reg = find_registry(cfg, "hosted")
    assert reg is not None
    assert resolve_registry_root(ROOT, reg) is None

    identity = registry_identity(ROOT, reg)
    assert identity["registry_kind"] == "http"
    assert identity["registry_base_url"] == "https://skills.example.com/registry"
    assert identity["registry_host"] == "skills.example.com"
    assert identity["registry_root"] is None
    assert identity.get("registry_commit") is None
    assert identity.get("registry_tag") is None
