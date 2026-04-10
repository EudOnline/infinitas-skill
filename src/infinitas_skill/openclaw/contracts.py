"""Contracts for the OpenClaw runtime profile."""

from __future__ import annotations

import json
from pathlib import Path


class OpenClawContractError(Exception):
    """Raised when the OpenClaw runtime profile is missing or invalid."""


def _require_nonempty_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpenClawContractError(f"{field} must be a non-empty string")
    return value.strip()


def _require_string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise OpenClawContractError(f"{field} must be a non-empty list")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise OpenClawContractError(f"{field} must contain only non-empty strings")
        items.append(item.strip())
    return items


def load_openclaw_runtime_profile(root: Path) -> dict:
    """Load and minimally validate the canonical OpenClaw runtime profile."""

    root = Path(root).resolve()
    path = root / "profiles" / "openclaw.json"
    if not path.is_file():
        raise OpenClawContractError(f"missing OpenClaw profile: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive parser guard
        raise OpenClawContractError(f"invalid JSON in {path}: {exc}") from exc

    _require_nonempty_string(payload.get("platform"), field="platform")
    if payload.get("platform") != "openclaw":
        raise OpenClawContractError(
            f"openclaw profile has wrong platform: {payload.get('platform')!r}"
        )

    runtime = payload.get("runtime")
    if not isinstance(runtime, dict):
        raise OpenClawContractError("runtime must be an object")
    _require_string_list(runtime.get("skill_dir_candidates"), field="runtime.skill_dir_candidates")
    entrypoint = _require_nonempty_string(runtime.get("entrypoint"), field="runtime.entrypoint")
    if entrypoint != "SKILL.md":
        raise OpenClawContractError("runtime.entrypoint must be SKILL.md")

    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        raise OpenClawContractError("capabilities must be an object")

    contract = payload.get("contract")
    if not isinstance(contract, dict):
        raise OpenClawContractError("contract must be an object")
    _require_string_list(contract.get("sources"), field="contract.sources")
    _require_nonempty_string(contract.get("last_verified"), field="contract.last_verified")

    return payload


__all__ = ["OpenClawContractError", "load_openclaw_runtime_profile"]
