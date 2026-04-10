from __future__ import annotations

from pathlib import Path
from typing import Any

from .decision_metadata import canonical_decision_metadata
from .memory_audit import MemoryAuditRecorder, emit_recommendation_memory_audit
from .recommendation_explanation import (
    annotate_ranked_recommendations,
    build_recommendation_explanation,
)
from .recommendation_memory import load_recommendation_memory_context
from .recommendation_ranking import (
    calculate_memory_signals,
    recommendation_reason,
    score_item,
    tokenize,
)
from .resolver import load_discovery_index


def _runtime_summary(item: dict[str, Any]) -> tuple[dict[str, Any], str, list[str]]:
    runtime = dict(item.get("runtime") or {})
    readiness = dict(runtime.get("readiness") or {})
    readiness_status = readiness.get("status")
    if not isinstance(readiness_status, str) or not readiness_status.strip():
        readiness_status = "ready" if readiness.get("ready") is True else "unknown"
    install_targets = runtime.get("install_targets")
    install_targets = install_targets if isinstance(install_targets, dict) else {}
    workspace_targets = list(install_targets.get("workspace") or [])
    if not workspace_targets:
        workspace_targets = [
            target
            for target in list(runtime.get("workspace_targets") or [])
            if isinstance(target, str)
            and target
            and not target.startswith("~/")
            and not Path(target).is_absolute()
        ]
    return runtime, readiness_status, workspace_targets


def recommend_skills(
    root: Path,
    task: str,
    target_agent: str | None = None,
    limit: int = 5,
    memory_provider: Any | None = None,
    memory_scope: dict | None = None,
    memory_context_enabled: bool = False,
    memory_top_k: int = 3,
    audit_recorder: MemoryAuditRecorder | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    payload = load_discovery_index(root)
    default_registry = payload.get("default_registry")
    task_tokens = tokenize(task)
    memory_context = load_recommendation_memory_context(
        task=task,
        target_agent=target_agent,
        memory_provider=memory_provider,
        memory_scope=memory_scope,
        memory_context_enabled=memory_context_enabled,
        memory_top_k=memory_top_k,
    )
    memory_records = memory_context.get("records") if isinstance(memory_context, dict) else []
    if not isinstance(memory_records, list):
        memory_records = []

    scored = []
    for item in payload.get("skills") or []:
        if not isinstance(item, dict):
            continue
        runtime, runtime_readiness, workspace_targets = _runtime_summary(item)
        scoring_item = dict(item)
        if target_agent == "openclaw":
            legacy = list(scoring_item.get("agent_compatible") or [])
            if (runtime.get("platform") == "openclaw") and (
                (runtime.get("readiness") or {}).get("ready") is True
            ):
                if "openclaw" not in legacy:
                    legacy.append("openclaw")
            scoring_item["agent_compatible"] = legacy
        score, factors = score_item(
            scoring_item,
            task_tokens=task_tokens,
            target_agent=target_agent,
            default_registry=default_registry,
        )
        memory_signals = calculate_memory_signals(
            scoring_item,
            factors=factors,
            records=memory_records,
        )
        score += memory_signals["applied_boost"]
        factors["memory_boost"] = memory_signals["applied_boost"]
        decision_metadata = canonical_decision_metadata(item)
        scored.append(
            (
                score,
                -(item.get("source_priority") or 0),
                item.get("qualified_name") or "",
                {
                    "name": item.get("name"),
                    "qualified_name": item.get("qualified_name"),
                    "publisher": item.get("publisher"),
                    "summary": item.get("summary"),
                    "source_registry": item.get("source_registry"),
                    "latest_version": item.get("latest_version"),
                    "trust_state": item.get("trust_state"),
                    "verified_support": item.get("verified_support") or {},
                    "install_requires_confirmation": item.get("install_requires_confirmation"),
                    "use_when": decision_metadata["use_when"],
                    "avoid_when": decision_metadata["avoid_when"],
                    "capabilities": decision_metadata["capabilities"],
                    "runtime_assumptions": decision_metadata["runtime_assumptions"],
                    "maturity": decision_metadata["maturity"],
                    "quality_score": decision_metadata["quality_score"],
                    "score": score,
                    "recommendation_reason": recommendation_reason(scoring_item, factors),
                    "ranking_factors": factors,
                    "memory_signals": memory_signals,
                    "runtime": runtime,
                    "runtime_readiness": runtime_readiness,
                    "workspace_targets": workspace_targets,
                    "plugin_needs": {"required": dict(runtime.get("plugin_capabilities") or {})},
                    "background_tasks": dict(
                        runtime.get("background_tasks") or {"required": False}
                    ),
                    "subagents": dict(runtime.get("subagents") or {"required": False}),
                },
            )
        )

    scored.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))
    annotate_ranked_recommendations(scored)
    visible = [entry[3] for entry in scored[: max(limit, 0)]]
    explanation = build_recommendation_explanation(
        scored=scored,
        visible=visible,
        memory_context=memory_context if isinstance(memory_context, dict) else None,
        memory_records_count=len(memory_records),
        memory_context_enabled=memory_context_enabled,
    )
    payload = {
        "ok": True,
        "task": task,
        "target_agent": target_agent,
        "results": visible,
        "explanation": explanation,
    }
    emit_recommendation_memory_audit(
        audit_recorder=audit_recorder,
        task=task,
        target_agent=target_agent,
        payload=payload,
    )
    return payload


__all__ = ["recommend_skills"]
