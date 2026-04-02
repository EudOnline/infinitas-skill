from pathlib import Path

from .decision_metadata import canonical_decision_metadata
from .resolver import load_discovery_index

TRUST_SCORES = {
    "verified": 3,
    "attested": 2,
    "installable": 1,
    "unknown": 0,
}

MATURITY_SCORES = {
    "stable": 3,
    "beta": 2,
    "experimental": 1,
    "unknown": 0,
}


def _tokenize(value: str | None) -> list[str]:
    if not isinstance(value, str):
        return []
    tokens = []
    for raw in value.lower().replace("/", " ").replace("-", " ").replace("_", " ").split():
        cleaned = raw.strip()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _match_strength(item: dict, task_tokens: list[str]) -> int:
    if not task_tokens:
        return 0
    texts = []
    for field in ["name", "qualified_name", "summary"]:
        value = item.get(field)
        if isinstance(value, str):
            texts.append(value.lower())
    for field in ["tags", "use_when", "capabilities"]:
        for value in item.get(field) or []:
            if isinstance(value, str):
                texts.append(value.lower())
    strength = 0
    for token in task_tokens:
        if any(token in text for text in texts):
            strength += 1
    return strength


def _freshness_score(value: str | None) -> int:
    if isinstance(value, str) and value.strip():
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits or "0")
    return 0


def _non_negative_gap(left: int | None, right: int | None) -> int:
    left_value = left if isinstance(left, int) else 0
    right_value = right if isinstance(right, int) else 0
    return abs(left_value - right_value)


def _compatibility_gap(top_factors: dict, current_factors: dict) -> str:
    top_compat = bool(top_factors.get("compatibility"))
    current_compat = bool(current_factors.get("compatibility"))
    if top_compat == current_compat:
        return "same"
    return "better" if current_compat else "worse"


def _confidence_view(
    *,
    factors: dict,
    rank: int,
    score_gap_from_top: int,
    score_gap_to_runner_up: int | None = None,
) -> dict:
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

    if strength >= 6:
        level = "high"
    elif strength >= 3:
        level = "medium"
    else:
        level = "low"

    return {"level": level, "reasons": reasons}


def _comparison_summary(winner: dict, runner_up: dict, score_gap: int) -> str:
    winner_signals = winner.get("comparative_signals") or {}
    return (
        f"{winner.get('qualified_name')} leads {runner_up.get('qualified_name')} "
        f"by {score_gap} score points; "
        f"quality gap {winner_signals.get('quality_gap_from_runner_up', 0)}, "
        f"freshness gap {winner_signals.get('verification_freshness_gap_from_runner_up', 0)}, "
        f"compatibility {winner_signals.get('compatibility_gap_from_runner_up', 'same')}"
    )


def _compatibility_signal(item: dict, *, target_agent: str | None) -> dict:
    if target_agent is None:
        return {
            "compatible": True,
            "bonus": 500,
            "mode": "unscoped",
            "state": None,
            "freshness_state": None,
        }

    verified_support = item.get("verified_support") or {}
    payload = verified_support.get(target_agent) if isinstance(verified_support, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    state = payload.get("state")
    freshness_state = payload.get("freshness_state")
    declared = target_agent in (item.get("agent_compatible") or [])

    if state in {"blocked", "broken", "unsupported"}:
        return {
            "compatible": False,
            "bonus": 0,
            "mode": "rejected",
            "state": state,
            "freshness_state": freshness_state,
        }
    if state in {"native", "adapted", "degraded"} and freshness_state == "fresh":
        return {
            "compatible": True,
            "bonus": 650,
            "mode": "fresh-verified",
            "state": state,
            "freshness_state": freshness_state,
        }
    if state in {"native", "adapted", "degraded"} and freshness_state == "stale":
        return {
            "compatible": True,
            "bonus": 450,
            "mode": "stale-verified",
            "state": state,
            "freshness_state": freshness_state,
        }
    if state in {"native", "adapted", "degraded"}:
        return {
            "compatible": True,
            "bonus": 550,
            "mode": "verified",
            "state": state,
            "freshness_state": freshness_state,
        }
    if declared:
        return {
            "compatible": True,
            "bonus": 350,
            "mode": "declared-only",
            "state": state,
            "freshness_state": freshness_state,
        }
    return {
        "compatible": False,
        "bonus": 0,
        "mode": "incompatible",
        "state": state,
        "freshness_state": freshness_state,
    }


def _score_item(
    item: dict,
    *,
    task_tokens: list[str],
    target_agent: str | None,
    default_registry: str,
) -> tuple[int, dict]:
    compatibility_signal = _compatibility_signal(item, target_agent=target_agent)
    compatibility = compatibility_signal["compatible"]
    private_preferred = item.get("source_registry") == default_registry
    match_strength = _match_strength(item, task_tokens)
    trust_score = TRUST_SCORES.get(item.get("trust_state") or "unknown", 0)
    maturity_score = MATURITY_SCORES.get(item.get("maturity") or "unknown", 0)
    quality_score = item.get("quality_score") if isinstance(item.get("quality_score"), int) else 0
    freshness = _freshness_score(item.get("last_verified_at"))

    score = (
        (1000 if private_preferred else 0)
        + compatibility_signal["bonus"]
        + (100 * match_strength)
        + (30 * trust_score)
        + (20 * maturity_score)
        + quality_score
    )
    factors = {
        "private_registry": private_preferred,
        "compatibility": compatibility,
        "compatibility_mode": compatibility_signal["mode"],
        "compatibility_state": compatibility_signal["state"],
        "compatibility_freshness": compatibility_signal["freshness_state"],
        "match_strength": match_strength,
        "trust": {
            "state": item.get("trust_state") or "unknown",
            "score": trust_score,
        },
        "maturity": item.get("maturity") or "unknown",
        "quality": quality_score,
        "verification_freshness": item.get("last_verified_at"),
        "verification_freshness_score": freshness,
    }
    return score, factors


def _recommendation_reason(item: dict, factors: dict) -> str:
    reasons = []
    if factors.get("private_registry"):
        reasons.append("private registry match")
    if factors.get("compatibility"):
        compatibility_mode = factors.get("compatibility_mode")
        if compatibility_mode == "fresh-verified":
            reasons.append("fresh verified target-agent compatibility")
        elif compatibility_mode == "stale-verified":
            reasons.append("stale verified target-agent compatibility")
        elif compatibility_mode == "declared-only":
            reasons.append("declared target-agent compatibility")
        else:
            reasons.append("target-agent compatible")
    if factors.get("match_strength"):
        reasons.append(f"matched {factors.get('match_strength')} task terms")
    trust = (factors.get("trust") or {}).get("state")
    if trust:
        reasons.append(f"trust state {trust}")
    quality = factors.get("quality")
    if isinstance(quality, int) and quality > 0:
        reasons.append(f"quality score {quality}")
    return "; ".join(reasons) or "deterministic fallback recommendation"


def recommend_skills(
    root: Path,
    task: str,
    target_agent: str | None = None,
    limit: int = 5,
) -> dict:
    root = Path(root).resolve()
    payload = load_discovery_index(root)
    default_registry = payload.get("default_registry")
    task_tokens = _tokenize(task)

    scored = []
    for item in payload.get("skills") or []:
        if not isinstance(item, dict):
            continue
        score, factors = _score_item(
            item,
            task_tokens=task_tokens,
            target_agent=target_agent,
            default_registry=default_registry,
        )
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
                    "recommendation_reason": _recommendation_reason(item, factors),
                    "ranking_factors": factors,
                },
            )
        )

    scored.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))
    visible = [entry[3] for entry in scored[: max(limit, 0)]]
    explanation = {}
    if scored:
        winner = scored[0][3]
        top_score = scored[0][0]
        top_factors = winner.get("ranking_factors") or {}
        runner_up = scored[1][3] if len(scored) > 1 else None
        runner_up_score = scored[1][0] if len(scored) > 1 else None
        score_gap_to_runner_up = (
            top_score - runner_up_score if runner_up_score is not None else None
        )

        for rank, entry in enumerate(scored, start=1):
            score, _, _, result = entry
            factors = result.get("ranking_factors") or {}
            score_gap_from_top = max(top_score - score, 0)
            result["comparative_signals"] = {
                "rank": rank,
                "score_gap_from_top": score_gap_from_top,
                "quality_gap_from_top": _non_negative_gap(
                    (
                        top_factors.get("quality")
                        if isinstance(top_factors.get("quality"), int)
                        else 0
                    ),
                    (factors.get("quality") if isinstance(factors.get("quality"), int) else 0),
                ),
                "verification_freshness_gap_from_top": _non_negative_gap(
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
                "compatibility_gap_from_top": _compatibility_gap(top_factors, factors),
            }
            if runner_up and rank == 1:
                runner_up_factors = runner_up.get("ranking_factors") or {}
                result["comparative_signals"]["quality_gap_from_runner_up"] = _non_negative_gap(
                    (factors.get("quality") if isinstance(factors.get("quality"), int) else 0),
                    (
                        runner_up_factors.get("quality")
                        if isinstance(runner_up_factors.get("quality"), int)
                        else 0
                    ),
                )
                result["comparative_signals"]["verification_freshness_gap_from_runner_up"] = (
                    _non_negative_gap(
                        (
                            factors.get("verification_freshness_score")
                            if isinstance(factors.get("verification_freshness_score"), int)
                            else 0
                        ),
                        (
                            runner_up_factors.get("verification_freshness_score")
                            if isinstance(
                                runner_up_factors.get("verification_freshness_score"), int
                            )
                            else 0
                        ),
                    )
                )
                result["comparative_signals"]["compatibility_gap_from_runner_up"] = (
                    _compatibility_gap(runner_up_factors, factors)
                )
            result["confidence"] = _confidence_view(
                factors=factors,
                rank=rank,
                score_gap_from_top=score_gap_from_top,
                score_gap_to_runner_up=score_gap_to_runner_up if rank == 1 else None,
            )

    results = visible
    if results:
        winner = results[0]
        runner_up = scored[1][3] if len(scored) > 1 else None
        winner_reason = winner.get("recommendation_reason") or "top deterministic recommendation"
        if runner_up:
            winner_reason = (
                f"{winner_reason}; outranked {runner_up.get('qualified_name')} via "
                f"private-first and deterministic ranking factors"
            )
        explanation = {
            "winner": winner.get("qualified_name"),
            "winner_reason": winner_reason,
            "runner_up": runner_up.get("qualified_name") if runner_up else None,
            "winner_confidence": winner.get("confidence"),
            "score_gap_to_runner_up": score_gap_to_runner_up if runner_up else None,
            "comparison_summary": (
                _comparison_summary(winner, runner_up, score_gap_to_runner_up)
                if runner_up and isinstance(score_gap_to_runner_up, int)
                else "only one eligible recommendation was available for comparison"
            ),
        }
    return {
        "ok": True,
        "task": task,
        "target_agent": target_agent,
        "results": results,
        "explanation": explanation,
    }
