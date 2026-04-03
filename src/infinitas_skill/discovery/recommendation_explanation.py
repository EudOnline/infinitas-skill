from __future__ import annotations

from typing import Any


def non_negative_gap(left: int | None, right: int | None) -> int:
    left_value = left if isinstance(left, int) else 0
    right_value = right if isinstance(right, int) else 0
    return abs(left_value - right_value)


def compatibility_gap(top_factors: dict[str, Any], current_factors: dict[str, Any]) -> str:
    top_compat = bool(top_factors.get("compatibility"))
    current_compat = bool(current_factors.get("compatibility"))
    if top_compat == current_compat:
        return "same"
    return "better" if current_compat else "worse"


def confidence_view(
    *,
    factors: dict[str, Any],
    rank: int,
    score_gap_from_top: int,
    score_gap_to_runner_up: int | None = None,
) -> dict[str, Any]:
    match_strength = (
        factors.get("match_strength") if isinstance(factors.get("match_strength"), int) else 0
    )
    compatibility = bool(factors.get("compatibility"))
    trust = factors.get("trust") if isinstance(factors.get("trust"), dict) else {}
    trust_score = trust.get("score") if isinstance(trust.get("score"), int) else 0
    quality_score = factors.get("quality") if isinstance(factors.get("quality"), int) else 0
    freshness_score = (
        factors.get("verification_freshness_score")
        if isinstance(factors.get("verification_freshness_score"), int)
        else 0
    )

    reasons = []
    strength = 0
    if compatibility:
        reasons.append("target-agent compatible")
        strength += 2
    if match_strength >= 3:
        reasons.append("strong task-term match")
        strength += 2
    elif match_strength > 0:
        reasons.append("matched task terms")
        strength += 1
    if trust_score >= 2:
        reasons.append("trusted verification state")
        strength += 1
    if quality_score >= 80:
        reasons.append("high quality score")
        strength += 1
    if freshness_score > 0:
        reasons.append("has verification freshness evidence")
        strength += 1

    if rank == 1:
        if isinstance(score_gap_to_runner_up, int) and score_gap_to_runner_up >= 200:
            reasons.append("clear score margin over runner-up")
            strength += 2
        elif isinstance(score_gap_to_runner_up, int) and score_gap_to_runner_up > 0:
            reasons.append("narrow lead over runner-up")
            strength += 1
    elif score_gap_from_top <= 75:
        reasons.append("close to the top-ranked option")
        strength += 1
    else:
        reasons.append("meaningfully trails the top-ranked option")

    level = "high" if strength >= 6 else "medium" if strength >= 3 else "low"
    return {"level": level, "reasons": reasons}


def comparison_summary(winner: dict[str, Any], runner_up: dict[str, Any], score_gap: int) -> str:
    winner_signals = winner.get("comparative_signals") or {}
    return (
        f"{winner.get('qualified_name')} leads {runner_up.get('qualified_name')} "
        f"by {score_gap} score points; "
        f"quality gap {winner_signals.get('quality_gap_from_runner_up', 0)}, "
        f"freshness gap {winner_signals.get('verification_freshness_gap_from_runner_up', 0)}, "
        f"compatibility {winner_signals.get('compatibility_gap_from_runner_up', 'same')}"
    )


def annotate_ranked_recommendations(
    scored: list[tuple[int, int, str, dict[str, Any]]],
) -> int | None:
    if not scored:
        return None
    top_score = scored[0][0]
    top_factors = scored[0][3].get("ranking_factors") or {}
    runner_up = scored[1][3] if len(scored) > 1 else None
    runner_up_score = scored[1][0] if len(scored) > 1 else None
    score_gap_to_runner_up = top_score - runner_up_score if runner_up_score is not None else None

    for rank, entry in enumerate(scored, start=1):
        score, _, _, result = entry
        factors = result.get("ranking_factors") or {}
        score_gap_from_top = max(top_score - score, 0)
        result["comparative_signals"] = {
            "rank": rank,
            "score_gap_from_top": score_gap_from_top,
            "quality_gap_from_top": non_negative_gap(
                top_factors.get("quality") if isinstance(top_factors.get("quality"), int) else 0,
                factors.get("quality") if isinstance(factors.get("quality"), int) else 0,
            ),
            "verification_freshness_gap_from_top": non_negative_gap(
                (
                    top_factors.get("verification_freshness_score")
                    if isinstance(top_factors.get("verification_freshness_score"), int)
                    else 0
                ),
                (
                    factors.get("verification_freshness_score")
                    if isinstance(factors.get("verification_freshness_score"), int)
                    else 0
                ),
            ),
            "compatibility_gap_from_top": compatibility_gap(top_factors, factors),
        }
        if runner_up and rank == 1:
            runner_up_factors = runner_up.get("ranking_factors") or {}
            result["comparative_signals"]["quality_gap_from_runner_up"] = non_negative_gap(
                factors.get("quality") if isinstance(factors.get("quality"), int) else 0,
                (
                    runner_up_factors.get("quality")
                    if isinstance(runner_up_factors.get("quality"), int)
                    else 0
                ),
            )
            result["comparative_signals"]["verification_freshness_gap_from_runner_up"] = (
                non_negative_gap(
                    (
                        factors.get("verification_freshness_score")
                        if isinstance(factors.get("verification_freshness_score"), int)
                        else 0
                    ),
                    (
                        runner_up_factors.get("verification_freshness_score")
                        if isinstance(runner_up_factors.get("verification_freshness_score"), int)
                        else 0
                    ),
                )
            )
            result["comparative_signals"]["compatibility_gap_from_runner_up"] = (
                compatibility_gap(runner_up_factors, factors)
            )
        result["confidence"] = confidence_view(
            factors=factors,
            rank=rank,
            score_gap_from_top=score_gap_from_top,
            score_gap_to_runner_up=score_gap_to_runner_up if rank == 1 else None,
        )

    return score_gap_to_runner_up


def build_recommendation_explanation(
    *,
    scored: list[tuple[int, int, str, dict[str, Any]]],
    visible: list[dict[str, Any]],
    memory_context: dict[str, Any] | None,
    memory_records_count: int,
    memory_context_enabled: bool,
) -> dict[str, Any]:
    explanation = {
        "memory_summary": {
            "used": bool(
                memory_context_enabled
                and any(
                    isinstance(entry[3].get("memory_signals"), dict)
                    and isinstance(entry[3]["memory_signals"].get("applied_boost"), int)
                    and entry[3]["memory_signals"]["applied_boost"] > 0
                    for entry in scored
                )
            ),
            "backend": (
                memory_context.get("backend") if isinstance(memory_context, dict) else "disabled"
            ),
            "matched_count": memory_records_count,
            "retrieved_count": (
                (memory_context.get("curation_summary") or {}).get("input_count")
                if isinstance(memory_context, dict)
                else 0
            ),
            "advisory_only": True,
            "status": (
                memory_context.get("status") if isinstance(memory_context, dict) else "disabled"
            ),
            "curation_summary": (
                dict(memory_context.get("curation_summary") or {})
                if isinstance(memory_context, dict)
                else {
                    "input_count": 0,
                    "kept_count": 0,
                    "suppressed_duplicates": 0,
                    "suppressed_low_signal": 0,
                }
            ),
        }
    }
    if isinstance(memory_context, dict):
        memory_error = memory_context.get("error")
        if isinstance(memory_error, str) and memory_error.strip():
            explanation["memory_summary"]["error"] = memory_error

    if not visible:
        return explanation

    winner = visible[0]
    runner_up = scored[1][3] if len(scored) > 1 else None
    score_gap_to_runner_up = (
        scored[0][0] - scored[1][0] if len(scored) > 1 else None
    )
    winner_reason = winner.get("recommendation_reason") or "top deterministic recommendation"
    if runner_up:
        winner_reason = (
            f"{winner_reason}; outranked {runner_up.get('qualified_name')} via "
            f"private-first and deterministic ranking factors"
        )
    explanation.update(
        {
            "winner": winner.get("qualified_name"),
            "winner_reason": winner_reason,
            "runner_up": runner_up.get("qualified_name") if runner_up else None,
            "winner_confidence": winner.get("confidence"),
            "score_gap_to_runner_up": score_gap_to_runner_up if runner_up else None,
            "comparison_summary": (
                comparison_summary(winner, runner_up, score_gap_to_runner_up)
                if runner_up and isinstance(score_gap_to_runner_up, int)
                else "only one eligible recommendation was available for comparison"
            ),
        }
    )
    return explanation


__all__ = [
    "annotate_ranked_recommendations",
    "build_recommendation_explanation",
    "comparison_summary",
    "confidence_view",
]
