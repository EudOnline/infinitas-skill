"""Registry source helpers used by install resolution."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from infinitas_skill.policy.policy_pack import load_effective_policy_domain

TRUST_TIERS = {"private", "trusted", "public", "untrusted"}
PIN_MODES = {"branch", "tag", "commit"}
UPDATE_MODES = {"local-only", "track", "pinned", "remote-only"}
AUTH_MODES = {"none", "token"}
FEDERATION_MODES = {"mirror", "federated"}
STALE_POLICIES = {"ignore", "warn", "fail"}
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
PUBLISHER_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def registry_sources_path(root: Path) -> Path:
    return root / "config" / "registry-sources.json"


def load_registry_config(root: Path):
    return load_effective_policy_domain(root, "registry_sources")


def registry_remote_url(reg):
    if not isinstance(reg, dict):
        return None
    for key in ["url", "base_url"]:
        value = reg.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_git_host(url):
    if not isinstance(url, str) or not url.strip():
        return None
    value = url.strip()
    if value.startswith("git@") and ":" in value:
        return value.split("@", 1)[1].split(":", 1)[0].lower()
    parsed = urlparse(value)
    if parsed.hostname:
        return parsed.hostname.lower()
    return None


def _clean_string_list(values):
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if item and item not in result:
            result.append(item)
    return result


def _clean_string_mapping(values):
    if not isinstance(values, dict):
        return {}
    result = {}
    for raw_key, raw_value in values.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            continue
        key = raw_key.strip()
        value = raw_value.strip()
        if key and value:
            result[key] = value
    return result


def _qualified_name(name, publisher=None, fallback=None):
    if isinstance(name, str) and name.strip():
        skill_name = name.strip()
        if isinstance(publisher, str) and publisher.strip():
            return f"{publisher.strip()}/{skill_name}"
        return skill_name
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return None


def short_pin_value(mode, value):
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


def canonical_pin_ref(mode, value):
    short = short_pin_value(mode, value)
    if not isinstance(short, str) or not short:
        return None
    if mode == "branch":
        return short if short.startswith("refs/heads/") else f"refs/heads/{short}"
    if mode == "tag":
        return short if short.startswith("refs/tags/") else f"refs/tags/{short}"
    return None


def normalized_pin(reg):
    pin = reg.get("pin") if isinstance(reg.get("pin"), dict) else {}
    if not pin and isinstance(reg.get("branch"), str) and reg.get("branch").strip():
        pin = {"mode": "branch", "value": reg.get("branch").strip()}
    mode = pin.get("mode")
    value = pin.get("value")
    if isinstance(value, str):
        value = value.strip()
    return {"mode": mode, "value": value}


def normalized_update_policy(reg):
    policy = reg.get("update_policy") if isinstance(reg.get("update_policy"), dict) else {}
    if reg.get("kind") == "http":
        mode = policy.get("mode", "remote-only")
        return {"mode": mode}
    default_mode = "local-only" if reg.get("kind") == "local" or reg.get("local_path") else "track"
    mode = policy.get("mode", default_mode)
    return {"mode": mode}


def normalized_auth(reg):
    auth = reg.get("auth") if isinstance(reg.get("auth"), dict) else {}
    mode = auth.get("mode", "none")
    env = auth.get("env")
    if isinstance(env, str):
        env = env.strip()
    return {"mode": mode, "env": env or None}


def normalized_federation(reg):
    federation = reg.get("federation") if isinstance(reg.get("federation"), dict) else {}
    mode = federation.get("mode")
    require_immutable_artifacts = federation.get("require_immutable_artifacts")
    return {
        "mode": mode,
        "allowed_publishers": _clean_string_list(federation.get("allowed_publishers")),
        "publisher_map": _clean_string_mapping(federation.get("publisher_map")),
        "require_immutable_artifacts": (
            require_immutable_artifacts if isinstance(require_immutable_artifacts, bool) else False
        ),
    }


def normalized_refresh_policy(reg):
    policy = reg.get("refresh_policy") if isinstance(reg.get("refresh_policy"), dict) else {}
    interval_hours = policy.get("interval_hours")
    max_cache_age_hours = policy.get("max_cache_age_hours")
    stale_policy = policy.get("stale_policy")
    return {
        "interval_hours": interval_hours if isinstance(interval_hours, int) else interval_hours,
        "max_cache_age_hours": (
            max_cache_age_hours if isinstance(max_cache_age_hours, int) else max_cache_age_hours
        ),
        "stale_policy": stale_policy,
    }


def registry_uses_refresh_cache(reg):
    if not isinstance(reg, dict):
        return False
    if reg.get("kind") != "git":
        return False
    if normalized_update_policy(reg).get("mode") == "local-only":
        return False
    policy = normalized_refresh_policy(reg)
    return any(
        policy.get(key) is not None
        for key in ["interval_hours", "max_cache_age_hours", "stale_policy"]
    )


def registry_is_resolution_candidate(reg, *, explicit_registry=False):
    mode = normalized_federation(reg).get("mode")
    if mode == "mirror" and not explicit_registry:
        return False
    return True


def apply_registry_federation(reg, item):
    if not isinstance(item, dict):
        return None

    clone = dict(item)
    federation = normalized_federation(reg)
    mode = federation.get("mode")
    upstream_publisher = clone.get("publisher")
    upstream_qualified_name = _qualified_name(
        clone.get("name"), upstream_publisher, fallback=clone.get("qualified_name")
    )

    clone["federation_mode"] = mode
    clone["upstream_publisher"] = upstream_publisher
    clone["upstream_qualified_name"] = upstream_qualified_name
    clone["publisher_mapping_applied"] = False

    if mode not in FEDERATION_MODES:
        return clone

    allowed_publishers = federation.get("allowed_publishers")
    if allowed_publishers and upstream_publisher not in allowed_publishers:
        return None

    local_publisher = federation.get("publisher_map", {}).get(
        upstream_publisher, upstream_publisher
    )
    clone["publisher"] = local_publisher
    clone["qualified_name"] = _qualified_name(
        clone.get("name"), local_publisher, fallback=upstream_qualified_name
    )
    clone["publisher_mapping_applied"] = clone.get("publisher") != upstream_publisher
    return clone


def normalized_allowed_hosts(reg):
    hosts = [value.lower() for value in _clean_string_list(reg.get("allowed_hosts"))]
    host = extract_git_host(registry_remote_url(reg))
    if not hosts and host:
        hosts = [host]
    return hosts


def normalized_allowed_refs(reg):
    refs = _clean_string_list(reg.get("allowed_refs"))
    pin = normalized_pin(reg)
    default_ref = canonical_pin_ref(pin.get("mode"), pin.get("value"))
    if not refs and default_ref:
        refs = [default_ref]
    return refs


def resolve_registry_root(root: Path, reg):
    local_path = reg.get("local_path")
    if local_path:
        path = Path(local_path)
        if not path.is_absolute():
            path = (root / path).resolve()
        return path
    if reg.get("kind") == "git":
        return (root / ".cache" / "registries" / reg.get("name")).resolve()
    if reg.get("name") == "self":
        return root
    return None


def _git_output(repo: Path, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def safe_git_output(repo: Path, *args):
    try:
        return _git_output(repo, *args)
    except Exception:
        return None


def git_repo_identity(repo: Path, preferred_tag=None):
    if not (repo / ".git").exists():
        return {
            "commit": None,
            "tag": None,
            "branch": None,
            "origin_url": None,
            "origin_host": None,
        }

    commit = safe_git_output(repo, "rev-parse", "HEAD")
    branch = safe_git_output(repo, "branch", "--show-current") or None
    tags_output = safe_git_output(repo, "tag", "--points-at", "HEAD") or ""
    tags = sorted(line.strip() for line in tags_output.splitlines() if line.strip())
    origin_url = safe_git_output(repo, "config", "--get", "remote.origin.url") or None
    tag = None
    if preferred_tag and preferred_tag in tags:
        tag = preferred_tag
    elif tags:
        tag = tags[0]
    return {
        "commit": commit,
        "tag": tag,
        "branch": branch,
        "origin_url": origin_url,
        "origin_host": extract_git_host(origin_url),
    }


def registry_identity(root: Path, reg):
    pin = normalized_pin(reg)
    update_policy = normalized_update_policy(reg)
    auth = normalized_auth(reg)
    federation = normalized_federation(reg)
    refresh_policy = normalized_refresh_policy(reg)
    reg_root = resolve_registry_root(root, reg)
    preferred_tag = (
        short_pin_value(pin.get("mode"), pin.get("value")) if pin.get("mode") == "tag" else None
    )
    remote_url = registry_remote_url(reg)
    if reg.get("kind") == "git" and reg_root and reg_root.exists():
        git_identity = git_repo_identity(reg_root, preferred_tag=preferred_tag)
    else:
        git_identity = {
            "commit": None,
            "tag": None,
            "branch": None,
            "origin_url": None,
            "origin_host": None,
        }
    return {
        "registry_name": reg.get("name"),
        "registry_kind": reg.get("kind"),
        "registry_url": remote_url,
        "registry_base_url": reg.get("base_url"),
        "registry_host": extract_git_host(remote_url),
        "registry_priority": reg.get("priority", 0),
        "registry_trust": reg.get("trust"),
        "registry_root": str(reg_root) if reg_root else None,
        "registry_pin_mode": pin.get("mode"),
        "registry_pin_value": pin.get("value"),
        "registry_ref": canonical_pin_ref(pin.get("mode"), pin.get("value")),
        "registry_allowed_refs": normalized_allowed_refs(reg),
        "registry_allowed_hosts": normalized_allowed_hosts(reg),
        "registry_update_mode": update_policy.get("mode"),
        "registry_auth_mode": auth.get("mode"),
        "registry_auth_env": auth.get("env"),
        "registry_federation_mode": federation.get("mode"),
        "registry_allowed_publishers": federation.get("allowed_publishers"),
        "registry_publisher_map": federation.get("publisher_map"),
        "registry_require_immutable_artifacts": federation.get("require_immutable_artifacts"),
        "registry_refresh_interval_hours": refresh_policy.get("interval_hours"),
        "registry_max_cache_age_hours": refresh_policy.get("max_cache_age_hours"),
        "registry_stale_policy": refresh_policy.get("stale_policy"),
        "registry_commit": git_identity.get("commit"),
        "registry_tag": git_identity.get("tag"),
        "registry_branch": git_identity.get("branch"),
        "registry_origin_url": git_identity.get("origin_url"),
        "registry_origin_host": git_identity.get("origin_host"),
    }


def find_registry(cfg, name):
    for reg in cfg.get("registries", []):
        if reg.get("name") == name:
            return reg
    return None


def validate_registry_config(root: Path, cfg):
    errors = []
    registries = cfg.get("registries")
    if not isinstance(registries, list) or not registries:
        errors.append("registries must be a non-empty array")
        return errors

    seen = set()
    for reg in registries:
        if not isinstance(reg, dict):
            errors.append("each registry entry must be an object")
            continue

        name = reg.get("name")
        kind = reg.get("kind")
        trust = reg.get("trust")
        local_path = reg.get("local_path")
        branch = reg.get("branch")
        pin = normalized_pin(reg)
        update_policy = normalized_update_policy(reg)
        federation = reg.get("federation")
        federation_cfg = normalized_federation(reg)
        refresh_policy = reg.get("refresh_policy")
        refresh_policy_cfg = normalized_refresh_policy(reg)
        allowed_refs = normalized_allowed_refs(reg)
        allowed_hosts = normalized_allowed_hosts(reg)

        if not isinstance(name, str) or not name:
            errors.append("registry name must be a non-empty string")
        elif name in seen:
            errors.append(f"duplicate registry name: {name}")
        else:
            seen.add(name)

        if kind not in {"git", "local", "http"}:
            errors.append(f"registry {name!r} kind must be git, local, or http")

        if trust not in TRUST_TIERS:
            errors.append(f"registry {name!r} trust must be one of {sorted(TRUST_TIERS)}")

        if "enabled" in reg and not isinstance(reg.get("enabled"), bool):
            errors.append(f"registry {name!r} enabled must be boolean")

        if "priority" in reg and not isinstance(reg.get("priority"), int):
            errors.append(f"registry {name!r} priority must be integer")

        if "notes" in reg and not isinstance(reg.get("notes"), str):
            errors.append(f"registry {name!r} notes must be a string")

        if refresh_policy is not None and not isinstance(refresh_policy, dict):
            errors.append(f"registry {name!r} refresh_policy must be an object when present")
        if isinstance(refresh_policy, dict):
            interval_hours = refresh_policy_cfg.get("interval_hours")
            max_cache_age_hours = refresh_policy_cfg.get("max_cache_age_hours")
            stale_policy = refresh_policy_cfg.get("stale_policy")

            if not isinstance(interval_hours, int) or interval_hours < 1:
                errors.append(
                    f"registry {name!r} refresh_policy.interval_hours must be a positive integer"
                )
            if not isinstance(max_cache_age_hours, int) or max_cache_age_hours < 1:
                errors.append(
                    "registry "
                    f"{name!r} refresh_policy.max_cache_age_hours must be a positive integer"
                )
            if (
                isinstance(interval_hours, int)
                and isinstance(max_cache_age_hours, int)
                and max_cache_age_hours < interval_hours
            ):
                errors.append(
                    "registry "
                    f"{name!r} refresh_policy.max_cache_age_hours must be greater than or "
                    "equal to refresh_policy.interval_hours"
                )
            if stale_policy not in STALE_POLICIES:
                errors.append(
                    "registry "
                    f"{name!r} refresh_policy.stale_policy must be one of "
                    f"{sorted(STALE_POLICIES)}"
                )

        if federation is not None and not isinstance(federation, dict):
            errors.append(f"registry {name!r} federation must be an object when present")
            federation = None
        if isinstance(federation, dict):
            if federation_cfg.get("mode") not in FEDERATION_MODES:
                errors.append(
                    f"registry {name!r} federation.mode must be one of {sorted(FEDERATION_MODES)}"
                )

            if federation.get("allowed_publishers") is not None:
                raw_publishers = federation.get("allowed_publishers")
                if not isinstance(raw_publishers, list) or not all(
                    isinstance(item, str) and item.strip() for item in raw_publishers
                ):
                    errors.append(
                        "registry "
                        f"{name!r} federation.allowed_publishers must be an array of "
                        "non-empty strings"
                    )
                else:
                    invalid_publishers = [
                        item.strip()
                        for item in raw_publishers
                        if not PUBLISHER_SLUG_RE.match(item.strip())
                    ]
                    if invalid_publishers:
                        errors.append(
                            "registry "
                            f"{name!r} federation.allowed_publishers must use valid "
                            "publisher slugs"
                        )

            if federation.get("publisher_map") is not None:
                raw_map = federation.get("publisher_map")
                if not isinstance(raw_map, dict):
                    errors.append(
                        f"registry {name!r} federation.publisher_map must be an object when present"
                    )
                else:
                    invalid_keys = []
                    invalid_values = []
                    for raw_key, raw_value in raw_map.items():
                        key = raw_key.strip() if isinstance(raw_key, str) else None
                        value = raw_value.strip() if isinstance(raw_value, str) else None
                        if not key or not PUBLISHER_SLUG_RE.match(key):
                            invalid_keys.append(raw_key)
                        if not value or not PUBLISHER_SLUG_RE.match(value):
                            invalid_values.append(raw_value)
                    if invalid_keys:
                        errors.append(
                            "registry "
                            f"{name!r} federation.publisher_map keys must be valid "
                            "publisher slugs"
                        )
                    if invalid_values:
                        errors.append(
                            "registry "
                            f"{name!r} federation.publisher_map values must be valid "
                            "publisher slugs"
                        )

            if federation.get("require_immutable_artifacts") is not None and not isinstance(
                federation.get("require_immutable_artifacts"), bool
            ):
                errors.append(
                    "registry "
                    f"{name!r} federation.require_immutable_artifacts must be boolean "
                    "when present"
                )

            reg_root = resolve_registry_root(root, reg)
            if reg_root == root:
                errors.append(f"registry {name!r} cannot federate the working repository root")

            if federation_cfg.get("mode") == "federated" and trust == "untrusted":
                errors.append(
                    f"registry {name!r} untrusted registries cannot use federation.mode='federated'"
                )

            if (
                federation_cfg.get("mode") == "federated"
                and kind == "git"
                and update_policy.get("mode") == "track"
            ):
                errors.append(
                    "registry "
                    f"{name!r} federated git registries cannot use "
                    "update_policy.mode='track'"
                )

            allowed_publishers = federation_cfg.get("allowed_publishers")
            publisher_map = federation_cfg.get("publisher_map")
            if allowed_publishers and publisher_map:
                outside = sorted(key for key in publisher_map if key not in allowed_publishers)
                if outside:
                    errors.append(
                        "registry "
                        f"{name!r} publisher_map keys must be listed in "
                        "federation.allowed_publishers"
                    )

        if kind == "git":
            url = reg.get("url")
            if not isinstance(url, str) or not url.strip():
                errors.append(f"git registry {name!r} missing non-empty url")
            if not isinstance(reg.get("pin"), dict):
                errors.append(f"git registry {name!r} missing pin object")
            if not isinstance(reg.get("update_policy"), dict):
                errors.append(f"git registry {name!r} missing update_policy object")

            if not isinstance(pin.get("mode"), str) or pin.get("mode") not in PIN_MODES:
                errors.append(f"registry {name!r} pin.mode must be one of {sorted(PIN_MODES)}")
            if not isinstance(pin.get("value"), str) or not pin.get("value"):
                errors.append(f"registry {name!r} pin.value must be a non-empty string")
            if (
                pin.get("mode") == "commit"
                and isinstance(pin.get("value"), str)
                and not COMMIT_RE.match(pin.get("value"))
            ):
                errors.append(f"registry {name!r} commit pins must use a full 40-character SHA")

            if branch is not None and (not isinstance(branch, str) or not branch.strip()):
                errors.append(f"registry {name!r} branch must be a non-empty string when set")
            if (
                branch
                and pin.get("mode") == "branch"
                and short_pin_value("branch", pin.get("value")) != branch.strip()
            ):
                errors.append(f"registry {name!r} branch must match pin.value for branch pins")

            if (
                not isinstance(update_policy.get("mode"), str)
                or update_policy.get("mode") not in UPDATE_MODES
            ):
                errors.append(
                    f"registry {name!r} update_policy.mode must be one of {sorted(UPDATE_MODES)}"
                )

            if reg.get("allowed_hosts") is not None:
                raw_hosts = reg.get("allowed_hosts")
                if not isinstance(raw_hosts, list) or not all(
                    isinstance(item, str) and item.strip() for item in raw_hosts
                ):
                    errors.append(
                        f"registry {name!r} allowed_hosts must be an array of non-empty strings"
                    )
            host = extract_git_host(url)
            if host and not allowed_hosts:
                errors.append(
                    f"registry {name!r} must declare allowed_hosts for remote git sources"
                )
            if host and host not in allowed_hosts:
                errors.append(
                    f"registry {name!r} url host {host!r} is not present in allowed_hosts"
                )

            if reg.get("allowed_refs") is not None:
                raw_refs = reg.get("allowed_refs")
                if not isinstance(raw_refs, list) or not all(
                    isinstance(item, str) and item.strip() for item in raw_refs
                ):
                    errors.append(
                        f"registry {name!r} allowed_refs must be an array of non-empty strings"
                    )
            desired_ref = canonical_pin_ref(pin.get("mode"), pin.get("value"))
            if pin.get("mode") in {"branch", "tag"}:
                if not allowed_refs:
                    errors.append(
                        f"registry {name!r} must declare allowed_refs for branch/tag pins"
                    )
                elif desired_ref not in allowed_refs:
                    errors.append(
                        f"registry {name!r} pin ref {desired_ref!r} must be "
                        "included in allowed_refs"
                    )

            if update_policy.get("mode") == "track" and pin.get("mode") != "branch":
                errors.append(f"registry {name!r} track policy requires a branch pin")
            if update_policy.get("mode") == "pinned" and pin.get("mode") not in {"tag", "commit"}:
                errors.append(f"registry {name!r} pinned policy requires a tag or commit pin")
            if update_policy.get("mode") == "local-only" and not local_path:
                errors.append(f"registry {name!r} local-only policy requires local_path")
            if local_path is not None and (
                not isinstance(local_path, str) or not local_path.strip()
            ):
                errors.append(f"registry {name!r} local_path must be a non-empty string when set")
            if local_path and update_policy.get("mode") != "local-only":
                errors.append(
                    "registry "
                    f"{name!r} git registries with local_path must use "
                    "update_policy.mode=local-only"
                )
            if trust == "public" and update_policy.get("mode") == "track":
                errors.append(
                    f"registry {name!r} public registries must use pinned or local-only updates"
                )
            if trust == "untrusted" and update_policy.get("mode") != "local-only":
                errors.append(
                    f"registry {name!r} untrusted registries may only use local-only mode"
                )

            reg_root = resolve_registry_root(root, reg)
            if local_path and reg_root == root and update_policy.get("mode") != "local-only":
                errors.append(
                    "registry "
                    f"{name!r} cannot sync the working repository root outside "
                    "local-only mode"
                )

        if kind == "local":
            if not isinstance(local_path, str) or not local_path.strip():
                errors.append(f"local registry {name!r} missing non-empty local_path")
            if reg.get("update_policy") is not None and update_policy.get("mode") != "local-only":
                errors.append(f"local registry {name!r} may only use update_policy.mode=local-only")

        if kind == "http":
            base_url = reg.get("base_url")
            if not isinstance(base_url, str) or not base_url.strip():
                errors.append(f"http registry {name!r} missing non-empty base_url")
            parsed_base = (
                urlparse(base_url.strip())
                if isinstance(base_url, str) and base_url.strip()
                else None
            )
            if parsed_base and not parsed_base.hostname:
                errors.append(f"registry {name!r} base_url must include a hostname")
            if (
                parsed_base
                and trust in {"private", "trusted", "public"}
                and parsed_base.scheme.lower() != "https"
            ):
                errors.append(f"registry {name!r} with trust {trust!r} must use an https base_url")

            auth = reg.get("auth")
            auth_cfg = normalized_auth(reg)
            if auth is not None and not isinstance(auth, dict):
                errors.append(f"registry {name!r} auth must be an object when present")
            if auth_cfg.get("mode") not in AUTH_MODES:
                errors.append(f"registry {name!r} auth.mode must be one of {sorted(AUTH_MODES)!r}")
            if auth_cfg.get("mode") == "token" and not auth_cfg.get("env"):
                errors.append(f"registry {name!r} token auth requires auth.env")
            if (
                auth_cfg.get("mode") == "none"
                and isinstance(auth, dict)
                and auth.get("env") not in {None, ""}
            ):
                errors.append(f"registry {name!r} auth.env must be omitted when auth.mode='none'")

            if reg.get("catalog_paths") is not None:
                catalog_paths = reg.get("catalog_paths")
                if not isinstance(catalog_paths, dict):
                    errors.append(f"registry {name!r} catalog_paths must be an object when present")
                else:
                    for key in ["ai_index", "distributions", "compatibility"]:
                        if key in catalog_paths and (
                            not isinstance(catalog_paths.get(key), str)
                            or not catalog_paths.get(key).strip()
                        ):
                            errors.append(
                                "registry "
                                f"{name!r} catalog_paths.{key} must be a non-empty "
                                "string when set"
                            )

    default_reg = cfg.get("default_registry")
    if default_reg is not None and default_reg not in seen:
        errors.append("default_registry must match one configured registry name")
    return errors
