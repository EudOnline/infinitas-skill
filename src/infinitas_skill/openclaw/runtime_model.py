"""OpenClaw runtime model builders."""

from __future__ import annotations

from pathlib import Path

from .contracts import load_openclaw_runtime_profile
from .plugins import normalize_plugin_capabilities


def build_openclaw_runtime_model(root: Path) -> dict:
    """Build a normalized runtime model from the OpenClaw profile."""

    profile = load_openclaw_runtime_profile(root)
    runtime = dict(profile.get("runtime") or {})
    contract = dict(profile.get("contract") or {})
    constraints = dict(profile.get("constraints") or {})

    plugin_capabilities = normalize_plugin_capabilities(constraints.get("plugin_capabilities"))

    return {
        "platform": profile.get("platform"),
        "entrypoint": runtime.get("entrypoint"),
        "skill_dir_candidates": list(runtime.get("skill_dir_candidates") or []),
        "workspace_state_dir": runtime.get("workspace_state_dir"),
        "session_store": runtime.get("session_store"),
        "capabilities": dict(profile.get("capabilities") or {}),
        "plugin_capabilities": plugin_capabilities,
        "constraints": constraints,
        "contract_sources": list(contract.get("sources") or []),
        "contract_last_verified": contract.get("last_verified"),
    }


__all__ = ["build_openclaw_runtime_model"]
