"""Complex validation rules for registry source configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infinitas_skill.install.registry_source_primitives import (
    COMMIT_RE,
    FEDERATION_MODES,
    PIN_MODES,
    PUBLISHER_SLUG_RE,
    UPDATE_MODES,
    canonical_pin_ref,
    extract_git_host,
    normalized_allowed_hosts,
    normalized_allowed_refs,
    normalized_federation,
    normalized_pin,
    normalized_update_policy,
    resolve_registry_root,
    short_pin_value,
)


def _validate_publisher_filters(
    federation: dict[str, Any], name: str, publisher_slug_re: Any
) -> list[str]:
    errors: list[str] = []
    raw_publishers = federation.get("allowed_publishers")
    if raw_publishers is not None:
        valid_list = isinstance(raw_publishers, list) and all(
            isinstance(item, str) and item.strip() for item in raw_publishers
        )
        if not valid_list:
            errors.append(
                f"registry {name!r} federation.allowed_publishers must be an array of "
                "non-empty strings"
            )
        elif any(not publisher_slug_re.match(item.strip()) for item in raw_publishers):
            errors.append(
                f"registry {name!r} federation.allowed_publishers must use valid publisher slugs"
            )
    raw_map = federation.get("publisher_map")
    if raw_map is not None and not isinstance(raw_map, dict):
        errors.append(f"registry {name!r} federation.publisher_map must be an object when present")
    elif isinstance(raw_map, dict):
        invalid_keys = [
            key
            for key in raw_map
            if not isinstance(key, str) or not publisher_slug_re.match(key.strip())
        ]
        invalid_values = [
            value
            for value in raw_map.values()
            if not isinstance(value, str) or not publisher_slug_re.match(value.strip())
        ]
        if invalid_keys:
            errors.append(
                f"registry {name!r} federation.publisher_map keys must be valid publisher slugs"
            )
        if invalid_values:
            errors.append(
                f"registry {name!r} federation.publisher_map values must be valid publisher slugs"
            )
    return errors


def validate_federation(
    reg: dict[str, Any],
    name: str,
    kind: str,
    trust: str,
    update_policy: dict[str, Any],
    root: Path,
) -> list[str]:
    errors: list[str] = []
    federation = reg.get("federation")
    config = normalized_federation(reg)
    if federation is not None and not isinstance(federation, dict):
        return [f"registry {name!r} federation must be an object when present"]
    if not isinstance(federation, dict):
        return errors
    if config.get("mode") not in FEDERATION_MODES:
        errors.append(
            f"registry {name!r} federation.mode must be one of {sorted(FEDERATION_MODES)}"
        )
    errors.extend(_validate_publisher_filters(federation, name, PUBLISHER_SLUG_RE))
    immutable = federation.get("require_immutable_artifacts")
    if immutable is not None and not isinstance(immutable, bool):
        errors.append(
            f"registry {name!r} federation.require_immutable_artifacts must be boolean when present"
        )
    if resolve_registry_root(root, reg) == root:
        errors.append(f"registry {name!r} cannot federate the working repository root")
    if config.get("mode") == "federated" and trust == "untrusted":
        errors.append(
            f"registry {name!r} untrusted registries cannot use federation.mode='federated'"
        )
    if config.get("mode") == "federated" and kind == "git" and update_policy.get("mode") == "track":
        errors.append(
            f"registry {name!r} federated git registries cannot use update_policy.mode='track'"
        )
    allowed = config.get("allowed_publishers")
    publisher_map = config.get("publisher_map")
    if allowed and publisher_map and any(key not in allowed for key in publisher_map):
        errors.append(
            f"registry {name!r} publisher_map keys must be listed in federation.allowed_publishers"
        )
    return errors


def _validate_git_pin_and_branch(reg: dict[str, Any], name: str) -> list[str]:
    errors: list[str] = []
    pin = normalized_pin(reg)
    branch = reg.get("branch")
    if not isinstance(reg.get("pin"), dict):
        errors.append(f"git registry {name!r} missing pin object")
    if pin.get("mode") not in PIN_MODES:
        errors.append(f"registry {name!r} pin.mode must be one of {sorted(PIN_MODES)}")
    value = pin.get("value")
    if not isinstance(value, str) or not value:
        errors.append(f"registry {name!r} pin.value must be a non-empty string")
    if pin.get("mode") == "commit" and isinstance(value, str) and not COMMIT_RE.match(value):
        errors.append(f"registry {name!r} commit pins must use a full 40-character SHA")
    if branch is not None and (not isinstance(branch, str) or not branch.strip()):
        errors.append(f"registry {name!r} branch must be a non-empty string when set")
    if isinstance(branch, str) and branch and pin.get("mode") == "branch":
        if short_pin_value("branch", value) != branch.strip():
            errors.append(f"registry {name!r} branch must match pin.value for branch pins")
    return errors


def _validate_git_allowlists(reg: dict[str, Any], name: str) -> list[str]:
    errors: list[str] = []
    hosts = normalized_allowed_hosts(reg)
    refs = normalized_allowed_refs(reg)
    pin = normalized_pin(reg)
    raw_hosts = reg.get("allowed_hosts")
    if raw_hosts is not None and (
        not isinstance(raw_hosts, list)
        or not all(isinstance(item, str) and item.strip() for item in raw_hosts)
    ):
        errors.append(f"registry {name!r} allowed_hosts must be an array of non-empty strings")
    host = extract_git_host(reg.get("url"))
    if host and not hosts:
        errors.append(f"registry {name!r} must declare allowed_hosts for remote git sources")
    if host and host not in hosts:
        errors.append(f"registry {name!r} url host {host!r} is not present in allowed_hosts")
    raw_refs = reg.get("allowed_refs")
    if raw_refs is not None and (
        not isinstance(raw_refs, list)
        or not all(isinstance(item, str) and item.strip() for item in raw_refs)
    ):
        errors.append(f"registry {name!r} allowed_refs must be an array of non-empty strings")
    desired_ref = canonical_pin_ref(pin.get("mode"), pin.get("value"))
    if pin.get("mode") in {"branch", "tag"} and not refs:
        errors.append(f"registry {name!r} must declare allowed_refs for branch/tag pins")
    elif pin.get("mode") in {"branch", "tag"} and desired_ref not in refs:
        errors.append(f"registry {name!r} pin ref {desired_ref!r} must be included in allowed_refs")
    return errors


def _validate_git_update_policy(
    reg: dict[str, Any], name: str, trust: str, root: Path
) -> list[str]:
    errors: list[str] = []
    local_path = reg.get("local_path")
    pin = normalized_pin(reg)
    policy = normalized_update_policy(reg)
    mode = policy.get("mode")
    if not isinstance(reg.get("update_policy"), dict):
        errors.append(f"git registry {name!r} missing update_policy object")
    if mode not in UPDATE_MODES:
        errors.append(f"registry {name!r} update_policy.mode must be one of {sorted(UPDATE_MODES)}")
    if mode == "track" and pin.get("mode") != "branch":
        errors.append(f"registry {name!r} track policy requires a branch pin")
    if mode == "pinned" and pin.get("mode") not in {"tag", "commit"}:
        errors.append(f"registry {name!r} pinned policy requires a tag or commit pin")
    if mode == "local-only" and not local_path:
        errors.append(f"registry {name!r} local-only policy requires local_path")
    if local_path is not None and (not isinstance(local_path, str) or not local_path.strip()):
        errors.append(f"registry {name!r} local_path must be a non-empty string when set")
    if local_path and mode != "local-only":
        errors.append(
            f"registry {name!r} git registries with local_path must use "
            "update_policy.mode=local-only"
        )
    if trust == "public" and mode == "track":
        errors.append(f"registry {name!r} public registries must use pinned or local-only updates")
    if trust == "untrusted" and mode != "local-only":
        errors.append(f"registry {name!r} untrusted registries may only use local-only mode")
    if local_path and resolve_registry_root(root, reg) == root and mode != "local-only":
        errors.append(
            f"registry {name!r} cannot sync the working repository root outside local-only mode"
        )
    return errors


def validate_git_registry(reg: dict[str, Any], name: str, trust: str, root: Path) -> list[str]:
    errors: list[str] = []
    url = reg.get("url")
    if not isinstance(url, str) or not url.strip():
        errors.append(f"git registry {name!r} missing non-empty url")
    errors.extend(_validate_git_pin_and_branch(reg, name))
    errors.extend(_validate_git_allowlists(reg, name))
    errors.extend(_validate_git_update_policy(reg, name, trust, root))
    return errors
