"""Registry refresh-state helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from infinitas_skill.install.registry_sources import (
    normalized_refresh_policy,
    resolve_registry_root,
)


def refresh_state_dir(root: Path) -> Path:
    return (root / ".cache" / "registries" / "_state").resolve()


def refresh_state_path(root: Path, registry_name: str) -> Path:
    return refresh_state_dir(root) / f"{registry_name}.json"


def utc_now_iso(now=None) -> str:
    current = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return (
        current.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def write_refresh_state(
    root: Path,
    *,
    registry_name: str,
    kind: str,
    cache_path: Path,
    source_commit: str,
    source_ref=None,
    source_tag=None,
    refreshed_at=None,
):
    payload = {
        "registry": registry_name,
        "kind": kind,
        "refreshed_at": refreshed_at or utc_now_iso(),
        "source_commit": source_commit,
        "source_ref": source_ref,
        "source_tag": source_tag,
        "cache_path": str(cache_path.resolve()),
    }
    path = refresh_state_path(root, registry_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, payload


def load_refresh_state(root: Path, registry_name: str):
    path = refresh_state_path(root, registry_name)
    if not path.exists():
        return path, None
    return path, json.loads(path.read_text(encoding="utf-8"))


def evaluate_refresh_status(root: Path, reg, *, now=None):
    registry_name = reg.get("name")
    state_path, state = load_refresh_state(root, registry_name)
    policy = normalized_refresh_policy(reg)
    now_dt = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    now_dt = now_dt.astimezone(timezone.utc)

    refreshed_at = parse_timestamp(state.get("refreshed_at")) if isinstance(state, dict) else None
    age_seconds = None
    age_hours = None
    if refreshed_at is not None:
        age_seconds = max(0.0, (now_dt - refreshed_at).total_seconds())
        age_hours = round(age_seconds / 3600.0, 6)

    interval_hours = policy.get("interval_hours")
    max_cache_age_hours = policy.get("max_cache_age_hours")
    stale_policy = policy.get("stale_policy")
    has_policy = any(
        value is not None for value in [interval_hours, max_cache_age_hours, stale_policy]
    )

    freshness_state = "not-configured"
    if has_policy and state is None:
        if stale_policy == "fail":
            freshness_state = "stale-fail"
        elif stale_policy == "warn":
            freshness_state = "stale-warning"
        elif stale_policy == "ignore":
            freshness_state = "stale-ignored"
        else:
            freshness_state = "missing-state"
    elif has_policy and refreshed_at is None:
        if stale_policy == "fail":
            freshness_state = "stale-fail"
        elif stale_policy == "warn":
            freshness_state = "stale-warning"
        elif stale_policy == "ignore":
            freshness_state = "stale-ignored"
        else:
            freshness_state = "missing-state"
    elif has_policy and age_hours is not None:
        if isinstance(max_cache_age_hours, int) and age_hours > max_cache_age_hours:
            if stale_policy == "fail":
                freshness_state = "stale-fail"
            elif stale_policy == "warn":
                freshness_state = "stale-warning"
            else:
                freshness_state = "stale-ignored"
        elif isinstance(interval_hours, int) and age_hours > interval_hours:
            freshness_state = "refresh-due"
        else:
            freshness_state = "fresh"

    cache_path = None
    if (
        isinstance(state, dict)
        and isinstance(state.get("cache_path"), str)
        and state.get("cache_path").strip()
    ):
        cache_path = state.get("cache_path").strip()
    else:
        reg_root = resolve_registry_root(root, reg)
        cache_path = str(reg_root.resolve()) if reg_root else None

    return {
        "registry": registry_name,
        "kind": reg.get("kind"),
        "has_state": state is not None,
        "state_file": str(state_path),
        "cache_path": cache_path,
        "refreshed_at": state.get("refreshed_at") if isinstance(state, dict) else None,
        "source_commit": state.get("source_commit") if isinstance(state, dict) else None,
        "source_ref": state.get("source_ref") if isinstance(state, dict) else None,
        "source_tag": state.get("source_tag") if isinstance(state, dict) else None,
        "refresh_interval_hours": interval_hours,
        "max_cache_age_hours": max_cache_age_hours,
        "stale_policy": stale_policy,
        "freshness_state": freshness_state,
        "age_seconds": age_seconds,
        "age_hours": age_hours,
    }


def _format_hours(value):
    if value is None:
        return "unknown age"
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return f"{int(rounded)}h"
    return f"{rounded}h"


def refresh_resolution_message(status):
    if not isinstance(status, dict):
        return None

    state = status.get("freshness_state")
    if state in {None, "fresh", "not-configured", "stale-ignored"}:
        return None

    registry_name = status.get("registry") or "unknown"
    refresh_command = f"scripts/sync-registry-source.sh {registry_name}"
    has_state = bool(status.get("has_state"))
    refreshed_at = status.get("refreshed_at")
    age_hours = status.get("age_hours")
    interval_hours = status.get("refresh_interval_hours")
    max_cache_age_hours = status.get("max_cache_age_hours")

    if state == "refresh-due":
        return (
            f"Registry '{registry_name}' cache refresh is due "
            f"({_format_hours(age_hours)} old, interval {interval_hours}h). "
            f"Run {refresh_command} to refresh it."
        )

    if not has_state or not refreshed_at:
        return (
            f"Registry '{registry_name}' has no recorded refresh state. "
            f"Run {refresh_command} to refresh it before relying on this cache."
        )

    return (
        f"Registry '{registry_name}' cache is stale "
        f"({_format_hours(age_hours)} old, max {max_cache_age_hours}h). "
        f"Run {refresh_command} to refresh it."
    )


def refresh_status_blocks_resolution(status):
    return isinstance(status, dict) and status.get("freshness_state") == "stale-fail"


__all__ = [
    "refresh_state_dir",
    "refresh_state_path",
    "utc_now_iso",
    "parse_timestamp",
    "write_refresh_state",
    "load_refresh_state",
    "evaluate_refresh_status",
    "refresh_resolution_message",
    "refresh_status_blocks_resolution",
]
