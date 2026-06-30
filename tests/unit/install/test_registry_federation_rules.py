from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from infinitas_skill.install.registry_sources import validate_registry_config

ROOT = Path(__file__).resolve().parents[3]


def _base_config(registry: dict) -> dict:
    return {
        "$schema": "../schemas/registry-sources.schema.json",
        "default_registry": registry["name"],
        "registries": [registry],
    }


def _federated_http_registry() -> dict:
    return {
        "name": "upstream-fed",
        "kind": "http",
        "base_url": "https://skills.example.com/registry",
        "enabled": True,
        "priority": 50,
        "trust": "trusted",
        "federation": {
            "mode": "federated",
            "allowed_publishers": ["partner"],
            "publisher_map": {"partner": "partner-labs"},
            "require_immutable_artifacts": True,
        },
    }


def _self_registry() -> dict:
    return {
        "name": "self",
        "kind": "git",
        "url": "https://github.com/EudOnline/infinitas-skill.git",
        "local_path": ".",
        "branch": "main",
        "priority": 100,
        "enabled": True,
        "trust": "private",
        "allowed_hosts": ["github.com"],
        "allowed_refs": ["refs/heads/main"],
        "pin": {"mode": "branch", "value": "main"},
        "update_policy": {"mode": "local-only"},
    }


def _tracked_git_registry() -> dict:
    return {
        "name": "tracked-upstream",
        "kind": "git",
        "url": "https://github.com/example/skills.git",
        "branch": "main",
        "priority": 80,
        "enabled": True,
        "trust": "trusted",
        "allowed_hosts": ["github.com"],
        "allowed_refs": ["refs/heads/main"],
        "pin": {"mode": "branch", "value": "main"},
        "update_policy": {"mode": "track"},
    }


def _errors(cfg: dict) -> list[str]:
    return validate_registry_config(ROOT, cfg)


def test_trusted_http_registry_accepts_federated_mode() -> None:
    assert _errors(_base_config(_federated_http_registry())) == []


def test_self_registry_rejects_federation_block() -> None:
    reg = _self_registry()
    reg["federation"] = {
        "mode": "federated",
        "allowed_publishers": ["lvxiaoer"],
        "publisher_map": {"lvxiaoer": "lvxiaoer"},
        "require_immutable_artifacts": True,
    }
    errors = _errors(_base_config(reg))
    assert errors and any("cannot federate the working repository root" in e for e in errors)


def test_untrusted_registry_rejects_federated_mode() -> None:
    reg = _federated_http_registry()
    reg["trust"] = "untrusted"
    errors = _errors(_base_config(reg))
    assert errors and any(
        "untrusted registries cannot use federation.mode='federated'" in e for e in errors
    )


def test_tracked_git_registry_rejects_federated_mode() -> None:
    reg = _tracked_git_registry()
    reg["federation"] = {
        "mode": "federated",
        "allowed_publishers": ["partner"],
        "publisher_map": {"partner": "partner-labs"},
        "require_immutable_artifacts": True,
    }
    errors = _errors(_base_config(reg))
    assert errors and any(
        "federated git registries cannot use update_policy.mode='track'" in e for e in errors
    )


def test_publisher_map_keys_must_stay_within_allowed_publishers() -> None:
    reg = _federated_http_registry()
    reg["federation"] = deepcopy(reg["federation"])
    reg["federation"]["publisher_map"] = {"partner": "partner-labs", "rogue": "rogue-local"}
    errors = _errors(_base_config(reg))
    assert errors and any(
        "publisher_map keys must be listed in federation.allowed_publishers" in e for e in errors
    )
