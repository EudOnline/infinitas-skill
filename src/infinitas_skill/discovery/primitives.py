from __future__ import annotations

import re

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+]([A-Za-z0-9_.-]+))?$")

_BLOCKING_COMPATIBILITY_STATES = {"blocked", "broken", "unsupported"}
_VERIFIED_COMPATIBILITY_STATES = {"native", "adapted", "degraded"}


def semver_key(value: object) -> tuple[int, int, int, int, str]:
    if not isinstance(value, str):
        return (-1, -1, -1, -1, "")
    match = SEMVER_RE.match(value.strip())
    if not match:
        return (-1, -1, -1, -1, value)
    major, minor, patch, suffix = match.groups()
    stability = 1 if suffix is None else 0
    return (int(major), int(minor), int(patch), stability, suffix or "")


def supports_target_agent(item: dict, target_agent: str | None) -> bool:
    if target_agent is None:
        return True

    verified_support = item.get("verified_support")
    verified_support = verified_support if isinstance(verified_support, dict) else {}
    payload = verified_support.get(target_agent)
    payload = payload if isinstance(payload, dict) else {}
    state = payload.get("state")
    if state in _BLOCKING_COMPATIBILITY_STATES:
        return False

    runtime = item.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}
    readiness = runtime.get("readiness")
    readiness = readiness if isinstance(readiness, dict) else {}
    if (
        target_agent == "openclaw"
        and runtime.get("platform") == "openclaw"
        and readiness.get("ready") is True
    ):
        return True
    if state in _VERIFIED_COMPATIBILITY_STATES:
        return True
    return target_agent in (item.get("agent_compatible") or [])
