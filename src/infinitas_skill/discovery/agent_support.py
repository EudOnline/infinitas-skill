from __future__ import annotations

BLOCKING_COMPATIBILITY_STATES = {"blocked", "broken", "unsupported"}
VERIFIED_COMPATIBILITY_STATES = {"native", "adapted", "degraded"}


def supports_target_agent(item: dict, target_agent: str | None) -> bool:
    if target_agent is None:
        return True

    verified_support = item.get("verified_support")
    verified_support = verified_support if isinstance(verified_support, dict) else {}
    payload = verified_support.get(target_agent)
    payload = payload if isinstance(payload, dict) else {}
    state = payload.get("state")
    if state in BLOCKING_COMPATIBILITY_STATES:
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

    if state in VERIFIED_COMPATIBILITY_STATES:
        return True

    return target_agent in (item.get("agent_compatible") or [])


__all__ = [
    "BLOCKING_COMPATIBILITY_STATES",
    "VERIFIED_COMPATIBILITY_STATES",
    "supports_target_agent",
]
