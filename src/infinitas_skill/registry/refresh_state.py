"""Registry refresh-state helpers."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infinitas_skill.install.registry_source_primitives import (
    normalized_refresh_policy,
    resolve_registry_root,
)
from infinitas_skill.registry._util import utc_now_iso

JsonDict = dict[str, Any]


def refresh_state_dir(root: Path) -> Path:
    return (root / ".cache" / "registries" / "_state").resolve()


def refresh_state_path(root: Path, registry_name: str) -> Path:
    return refresh_state_dir(root) / f"{registry_name}.json"


def parse_timestamp(value: object) -> datetime | None:
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
    source_ref: str | None = None,
    source_tag: str | None = None,
    refreshed_at: str | None = None,
) -> tuple[Path, JsonDict]:
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
    fd, raw_tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(raw_tmp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return path, payload


def load_refresh_state(root: Path, registry_name: str) -> tuple[Path, JsonDict | None]:
    path = refresh_state_path(root, registry_name)
    if not path.exists():
        return path, None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return path, None
    return path, payload


def evaluate_refresh_status(root: Path, reg: JsonDict, *, now: datetime | None = None) -> JsonDict:
    registry_name = reg.get("name")
    if not isinstance(registry_name, str) or not registry_name:
        raise ValueError("registry is missing name")
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

    freshness_state = _freshness_state(
        has_policy=has_policy,
        has_timestamp=refreshed_at is not None,
        age_hours=age_hours,
        interval_hours=interval_hours,
        max_cache_age_hours=max_cache_age_hours,
        stale_policy=stale_policy,
    )
    cache_path = _cache_path(root, reg, state)

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


def _stale_state(stale_policy: object, *, missing: bool = False) -> str:
    states = {
        "fail": "stale-fail",
        "warn": "stale-warning",
        "ignore": "stale-ignored",
    }
    return states.get(
        stale_policy if isinstance(stale_policy, str) else "",
        "missing-state" if missing else "stale-ignored",
    )


def _freshness_state(
    *,
    has_policy: bool,
    has_timestamp: bool,
    age_hours: float | None,
    interval_hours: object,
    max_cache_age_hours: object,
    stale_policy: object,
) -> str:
    if not has_policy:
        return "not-configured"
    if not has_timestamp:
        return _stale_state(stale_policy, missing=True)
    cache_expired = (
        isinstance(max_cache_age_hours, int)
        and age_hours is not None
        and age_hours > max_cache_age_hours
    )
    if cache_expired:
        return _stale_state(stale_policy)
    if isinstance(interval_hours, int) and age_hours is not None and age_hours > interval_hours:
        return "refresh-due"
    return "fresh"


def _cache_path(root: Path, reg: JsonDict, state: JsonDict | None) -> str | None:
    value = state.get("cache_path") if isinstance(state, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    reg_root = resolve_registry_root(root, reg)
    return str(reg_root.resolve()) if reg_root else None


def _format_hours(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "unknown age"
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return f"{int(rounded)}h"
    return f"{rounded}h"


def refresh_resolution_message(status: object) -> str | None:
    if not isinstance(status, dict):
        return None

    state = status.get("freshness_state")
    if state in {None, "fresh", "not-configured", "stale-ignored"}:
        return None

    registry_name = status.get("registry") or "unknown"
    refresh_command = f"infinitas registry sources sync {registry_name}"
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


def refresh_status_blocks_resolution(status: object) -> bool:
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
