from __future__ import annotations

from typing import Any


def _ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 3)


def build_recommendation_usefulness_outcome(
    case: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    result = results[0] if results else {}
    explanation = payload.get("explanation") if isinstance(payload.get("explanation"), dict) else {}
    memory_summary = (
        explanation.get("memory_summary")
        if isinstance(explanation.get("memory_summary"), dict)
        else {}
    )
    winner_match = result.get("qualified_name") == case.get("expected_winner")
    memory_enabled = bool(case.get("memory_context_enabled"))
    used = bool(memory_summary.get("used"))
    beneficial_use = (
        memory_enabled
        and bool(case.get("expected_memory_used"))
        and used
        and winner_match
    )
    correct_restraint = (
        memory_enabled
        and (not bool(case.get("expected_memory_used")))
        and (not used)
        and winner_match
    )
    curation_summary = (
        memory_summary.get("curation_summary")
        if isinstance(memory_summary.get("curation_summary"), dict)
        else {}
    )
    return {
        "mode": "recommendation",
        "name": case.get("name"),
        "memory_enabled": memory_enabled,
        "winner_match": winner_match,
        "beneficial_use": beneficial_use,
        "correct_restraint": correct_restraint,
        "quality_success": beneficial_use or correct_restraint,
        "curation_kept": int(curation_summary.get("kept_count") or 0) > 0,
    }


def build_inspect_usefulness_outcome(
    case: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    memory_hints = (
        payload.get("memory_hints")
        if isinstance(payload.get("memory_hints"), dict)
        else {}
    )
    items = memory_hints.get("items") if isinstance(memory_hints.get("items"), list) else []
    first_item = items[0] if items else {}
    trust_match = payload.get("trust_state") == case.get("expected_trust_state")
    first_hint_match = first_item.get("memory_type") == case.get("expected_first_memory_type")
    curation_summary = (
        memory_hints.get("curation_summary")
        if isinstance(memory_hints.get("curation_summary"), dict)
        else {}
    )
    memory_enabled = bool(case.get("memory_context_enabled"))
    beneficial_use = memory_enabled and trust_match and first_hint_match
    return {
        "mode": "inspect",
        "name": case.get("name"),
        "memory_enabled": memory_enabled,
        "trust_match": trust_match,
        "first_hint_match": first_hint_match,
        "beneficial_use": beneficial_use,
        "correct_restraint": False,
        "quality_success": beneficial_use,
        "curation_kept": int(curation_summary.get("kept_count") or 0) > 0,
    }


def _summarize_mode(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    cases = len(outcomes)
    memory_enabled_cases = sum(1 for item in outcomes if item.get("memory_enabled"))
    beneficial_use_cases = sum(1 for item in outcomes if item.get("beneficial_use"))
    correct_restraint_cases = sum(1 for item in outcomes if item.get("correct_restraint"))
    quality_success_cases = sum(1 for item in outcomes if item.get("quality_success"))
    curation_kept_cases = sum(1 for item in outcomes if item.get("curation_kept"))
    denominator = memory_enabled_cases or cases
    return {
        "cases": cases,
        "memory_enabled_cases": memory_enabled_cases,
        "beneficial_use_cases": beneficial_use_cases,
        "correct_restraint_cases": correct_restraint_cases,
        "quality_success_cases": quality_success_cases,
        "quality_success_rate": _ratio(quality_success_cases, denominator),
        "curation_keep_rate": _ratio(curation_kept_cases, denominator),
    }


def summarize_memory_usefulness(
    *,
    recommendation_outcomes: list[dict[str, Any]],
    inspect_outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    recommendation_summary = _summarize_mode(recommendation_outcomes)
    inspect_summary = _summarize_mode(inspect_outcomes)
    overall_summary = _summarize_mode(list(recommendation_outcomes) + list(inspect_outcomes))
    return {
        "recommendation": recommendation_summary,
        "inspect": inspect_summary,
        "overall": overall_summary,
    }


__all__ = [
    "build_inspect_usefulness_outcome",
    "build_recommendation_usefulness_outcome",
    "summarize_memory_usefulness",
]
