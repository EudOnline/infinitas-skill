"""Discovery search helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .agent_support import supports_target_agent
from .decision_metadata import canonical_decision_metadata


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_discovery_index(root: Path):
    return _load_json(root / "catalog" / "discovery-index.json")


def _compatibility_freshness_summary(verified_support: dict) -> dict:
    summary = {}
    for platform, payload in (verified_support or {}).items():
        if not isinstance(platform, str) or not platform.strip():
            continue
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("freshness_state"), str)
            and payload.get("freshness_state").strip()
        ):
            summary[platform] = payload.get("freshness_state")
    return summary


def search_skills(
    root: Path,
    query: str | None = None,
    publisher: str | None = None,
    agent: str | None = None,
    tag: str | None = None,
) -> dict:
    root = Path(root).resolve()
    payload = _load_discovery_index(root)
    lowered_query = (query or "").strip().lower()
    results = []
    for item in payload.get("skills") or []:
        if not isinstance(item, dict):
            continue
        if lowered_query:
            haystacks = [item.get("name") or "", item.get("qualified_name") or ""]
            haystacks.extend(item.get("match_names") or [])
            if not any(
                lowered_query in value.lower() for value in haystacks if isinstance(value, str)
            ):
                continue
        if publisher and item.get("publisher") != publisher:
            continue
        if agent and not supports_target_agent(item, agent):
            continue
        if tag and tag not in (item.get("tags") or []):
            continue
        result = {
            "name": item.get("name"),
            "qualified_name": item.get("qualified_name"),
            "publisher": item.get("publisher"),
            "summary": item.get("summary"),
            "latest_version": item.get("latest_version"),
            "trust_state": item.get("trust_state"),
            "verified_support": item.get("verified_support") or {},
            "freshness_summary": _compatibility_freshness_summary(
                item.get("verified_support") or {}
            ),
            "agent_compatible": item.get("agent_compatible") or [],
            "tags": item.get("tags") or [],
            "attestation_formats": item.get("attestation_formats") or [],
            "source_registry": item.get("source_registry"),
        }
        result.update(canonical_decision_metadata(item))
        results.append(result)
    return {
        "ok": True,
        "query": query,
        "publisher": publisher,
        "agent": agent,
        "tag": tag,
        "results": results,
    }


__all__ = ["search_skills"]
