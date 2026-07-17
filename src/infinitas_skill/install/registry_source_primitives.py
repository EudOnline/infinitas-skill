"""Pure registry-source normalization and path primitives."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

TRUST_TIERS = {"private", "trusted", "public", "untrusted"}
PIN_MODES = {"branch", "tag", "commit"}
UPDATE_MODES = {"local-only", "track", "pinned", "remote-only"}
AUTH_MODES = {"none", "token"}
FEDERATION_MODES = {"mirror", "federated"}
STALE_POLICIES = {"ignore", "warn", "fail"}
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
PUBLISHER_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def registry_remote_url(registry: dict[str, Any]) -> str | None:
    for key in ["url", "base_url"]:
        value = registry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_git_host(url: object) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    value = url.strip()
    if value.startswith("git@") and ":" in value:
        return value.split("@", 1)[1].split(":", 1)[0].lower()
    parsed = urlparse(value)
    return parsed.hostname.lower() if parsed.hostname else None


def _clean_string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if item and item not in result:
            result.append(item)
    return result


def _clean_string_mapping(values: object) -> dict[str, str]:
    if not isinstance(values, dict):
        return {}
    result: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            continue
        key = raw_key.strip()
        value = raw_value.strip()
        if key and value:
            result[key] = value
    return result


def qualified_name(name: object, publisher: object = None, fallback: object = None) -> str | None:
    if isinstance(name, str) and name.strip():
        skill_name = name.strip()
        if isinstance(publisher, str) and publisher.strip():
            return f"{publisher.strip()}/{skill_name}"
        return skill_name
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return None


def short_pin_value(mode: object, value: object) -> object:
    if not isinstance(value, str):
        return value
    item = value.strip()
    if mode == "branch" and item.startswith("refs/heads/"):
        return item[len("refs/heads/") :]
    if mode == "tag" and item.startswith("refs/tags/"):
        return item[len("refs/tags/") :]
    if mode == "branch" and item.startswith("origin/"):
        return item.split("/", 1)[1]
    return item


def canonical_pin_ref(mode: object, value: object) -> str | None:
    short = short_pin_value(mode, value)
    if not isinstance(short, str) or not short:
        return None
    if mode == "branch":
        return short if short.startswith("refs/heads/") else f"refs/heads/{short}"
    if mode == "tag":
        return short if short.startswith("refs/tags/") else f"refs/tags/{short}"
    return None


def normalized_pin(registry: dict[str, Any]) -> dict[str, Any]:
    raw_pin = registry.get("pin")
    pin = raw_pin if isinstance(raw_pin, dict) else {}
    branch = registry.get("branch")
    if not pin and isinstance(branch, str) and branch.strip():
        pin = {"mode": "branch", "value": branch.strip()}
    mode = pin.get("mode")
    value = pin.get("value")
    if isinstance(value, str):
        value = value.strip()
    return {"mode": mode, "value": value}


def normalized_update_policy(registry: dict[str, Any]) -> dict[str, Any]:
    raw_policy = registry.get("update_policy")
    policy = raw_policy if isinstance(raw_policy, dict) else {}
    if registry.get("kind") == "http":
        return {"mode": policy.get("mode", "remote-only")}
    default_mode = (
        "local-only" if registry.get("kind") == "local" or registry.get("local_path") else "track"
    )
    return {"mode": policy.get("mode", default_mode)}


def normalized_auth(registry: dict[str, Any]) -> dict[str, Any]:
    raw_auth = registry.get("auth")
    auth = raw_auth if isinstance(raw_auth, dict) else {}
    mode = auth.get("mode", "none")
    env = auth.get("env")
    if isinstance(env, str):
        env = env.strip()
    return {"mode": mode, "env": env or None}


def normalized_federation(registry: dict[str, Any]) -> dict[str, Any]:
    raw_federation = registry.get("federation")
    federation = raw_federation if isinstance(raw_federation, dict) else {}
    immutable = federation.get("require_immutable_artifacts")
    return {
        "mode": federation.get("mode"),
        "allowed_publishers": _clean_string_list(federation.get("allowed_publishers")),
        "publisher_map": _clean_string_mapping(federation.get("publisher_map")),
        "require_immutable_artifacts": immutable if isinstance(immutable, bool) else False,
    }


def normalized_refresh_policy(registry: dict[str, Any]) -> dict[str, Any]:
    raw_policy = registry.get("refresh_policy")
    policy = raw_policy if isinstance(raw_policy, dict) else {}
    return {
        "interval_hours": policy.get("interval_hours"),
        "max_cache_age_hours": policy.get("max_cache_age_hours"),
        "stale_policy": policy.get("stale_policy"),
    }


def normalized_allowed_hosts(registry: dict[str, Any]) -> list[str]:
    hosts = [value.lower() for value in _clean_string_list(registry.get("allowed_hosts"))]
    host = extract_git_host(registry_remote_url(registry))
    return hosts or ([host] if host else [])


def normalized_allowed_refs(registry: dict[str, Any]) -> list[str]:
    refs = _clean_string_list(registry.get("allowed_refs"))
    pin = normalized_pin(registry)
    default_ref = canonical_pin_ref(pin.get("mode"), pin.get("value"))
    return refs or ([default_ref] if default_ref else [])


def resolve_registry_root(root: Path, registry: dict[str, Any]) -> Path | None:
    local_path = registry.get("local_path")
    if local_path:
        path = Path(local_path)
        return path if path.is_absolute() else (root / path).resolve()
    if registry.get("kind") == "git":
        name = registry.get("name")
        return (
            (root / ".cache" / "registries" / name).resolve()
            if isinstance(name, str) and name
            else None
        )
    if registry.get("name") == "self":
        return root
    return None
