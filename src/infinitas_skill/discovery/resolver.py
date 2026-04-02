import json
from pathlib import Path

from infinitas_skill.install.registry_sources import load_registry_config

from .ai_index import validate_ai_index_payload
from .index import build_discovery_index, validate_discovery_index_payload


def load_discovery_index(root: Path) -> dict:
    root = Path(root).resolve()
    cfg = load_registry_config(root)
    should_build_dynamic = any(
        reg.get("enabled", True) and reg.get("kind") == "http" for reg in cfg.get("registries", [])
    )
    path = root / "catalog" / "discovery-index.json"
    if not should_build_dynamic and path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        ai_index_path = root / "catalog" / "ai-index.json"
        if not ai_index_path.exists():
            raise ValueError(f"missing AI index: {ai_index_path}")
        local_ai_index = json.loads(ai_index_path.read_text(encoding="utf-8"))
        ai_errors = validate_ai_index_payload(local_ai_index)
        if ai_errors:
            raise ValueError("; ".join(ai_errors))
        payload = build_discovery_index(
            root=root,
            local_ai_index=local_ai_index,
            registry_config=cfg,
        )
    errors = validate_discovery_index_payload(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return payload


def filter_candidates(skills: list, query: str) -> list:
    query = (query or "").strip()
    matches = []
    for skill in skills or []:
        if not isinstance(skill, dict):
            continue
        names = skill.get("match_names") or []
        if query == skill.get("qualified_name") or query == skill.get("name") or query in names:
            matches.append(skill)
    return matches


def filter_by_agent(candidates: list, target_agent: str | None) -> list:
    if not target_agent:
        return list(candidates)
    return [
        candidate
        for candidate in candidates
        if target_agent in (candidate.get("agent_compatible") or [])
    ]


def rank_candidates(
    candidates: list,
    *,
    default_registry: str,
    target_agent: str | None = None,
    query: str | None = None,
) -> list:
    exact_query = (query or "").strip()
    return sorted(
        candidates,
        key=lambda item: (
            item.get("source_registry") != default_registry,
            exact_query not in {item.get("name"), item.get("qualified_name")},
            target_agent is not None and target_agent not in (item.get("agent_compatible") or []),
            -(item.get("source_priority") or 0),
            item.get("qualified_name") or "",
        ),
    )


def candidate_view(item: dict) -> dict:
    return {
        "name": item.get("name"),
        "qualified_name": item.get("qualified_name"),
        "source_registry": item.get("source_registry"),
        "resolved_version": item.get("default_install_version") or item.get("latest_version"),
        "install_requires_confirmation": item.get("install_requires_confirmation"),
    }


def resolve_skill(*, payload: dict, query: str, target_agent: str | None = None) -> dict:
    default_registry = payload.get("default_registry")
    all_candidates = filter_candidates(payload.get("skills") or [], query)
    private_candidates = [
        item for item in all_candidates if item.get("source_registry") == default_registry
    ]
    private_compatible = filter_by_agent(private_candidates, target_agent)

    if len(private_compatible) == 1:
        resolved = candidate_view(
            rank_candidates(
                private_compatible,
                default_registry=default_registry,
                target_agent=target_agent,
                query=query,
            )[0]
        )
        return {
            "ok": True,
            "query": query,
            "state": "resolved-private",
            "resolved": resolved,
            "candidates": [],
            "requires_confirmation": False,
            "recommended_next_step": "run install-by-name",
        }

    if len(private_compatible) > 1:
        ranked = rank_candidates(
            private_compatible,
            default_registry=default_registry,
            target_agent=target_agent,
            query=query,
        )
        return {
            "ok": True,
            "query": query,
            "state": "ambiguous",
            "resolved": None,
            "candidates": [candidate_view(item) for item in ranked],
            "requires_confirmation": True,
            "recommended_next_step": "choose a qualified_name",
        }

    external_candidates = [
        item for item in all_candidates if item.get("source_registry") != default_registry
    ]
    external_compatible = filter_by_agent(external_candidates, target_agent)

    if len(external_compatible) == 1:
        resolved = candidate_view(
            rank_candidates(
                external_compatible,
                default_registry=default_registry,
                target_agent=target_agent,
                query=query,
            )[0]
        )
        return {
            "ok": True,
            "query": query,
            "state": "resolved-external",
            "resolved": resolved,
            "candidates": [],
            "requires_confirmation": True,
            "recommended_next_step": "confirm and run install-by-name",
        }

    if len(external_compatible) > 1:
        ranked = rank_candidates(
            external_compatible,
            default_registry=default_registry,
            target_agent=target_agent,
            query=query,
        )
        return {
            "ok": True,
            "query": query,
            "state": "ambiguous",
            "resolved": None,
            "candidates": [candidate_view(item) for item in ranked],
            "requires_confirmation": True,
            "recommended_next_step": "choose a qualified_name",
        }

    if all_candidates:
        ranked = rank_candidates(
            all_candidates,
            default_registry=default_registry,
            target_agent=target_agent,
            query=query,
        )
        return {
            "ok": True,
            "query": query,
            "state": "incompatible",
            "resolved": None,
            "candidates": [candidate_view(item) for item in ranked],
            "requires_confirmation": False,
            "recommended_next_step": "pick a compatible skill or target agent",
        }

    return {
        "ok": True,
        "query": query,
        "state": "not-found",
        "resolved": None,
        "candidates": [],
        "requires_confirmation": False,
        "recommended_next_step": "check discovery-index or use a qualified_name",
    }
