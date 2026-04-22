from __future__ import annotations

from typing import Any

from infinitas_skill.memory import effective_memory_score
from infinitas_skill.memory.contracts import MemoryRecord

from .agent_support import supports_target_agent

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

MEMORY_TYPE_BOOSTS = {
    "user_preference": 22,
    "task_context": 16,
    "experience": 12,
}
MEMORY_MAX_BOOST = 35
MEMORY_MIN_TOKEN_LENGTH = 4
MEMORY_TOKEN_STOPWORDS = {
    "and",
    "artifact",
    "artifacts",
    "codex",
    "for",
    "helper",
    "helpers",
    "install",
    "need",
    "ready",
    "release",
    "released",
    "skill",
    "skills",
    "stable",
    "task",
    "the",
    "workflow",
    "workflows",
}
NEGATIVE_EXPERIENCE_TERMS = {
    "blocked",
    "break",
    "broken",
    "crash",
    "crashes",
    "denied",
    "error",
    "errors",
    "fail",
    "failed",
    "failing",
    "fails",
    "rejected",
    "rejects",
    "unsafe",
    "unsupported",
}


def tokenize(value: str | None) -> list[str]:
    if not isinstance(value, str):
        return []
    tokens = []
    for raw in value.lower().replace("/", " ").replace("-", " ").replace("_", " ").split():
        cleaned = raw.strip()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def match_strength(item: dict[str, Any], task_tokens: list[str]) -> int:
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


def freshness_score(value: str | None) -> int:
    if isinstance(value, str) and value.strip():
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits or "0")
    return 0


def compatibility_signal(item: dict[str, Any], *, target_agent: str | None) -> dict[str, Any]:
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
    runtime = item.get("runtime") if isinstance(item.get("runtime"), dict) else {}
    readiness = runtime.get("readiness") if isinstance(runtime.get("readiness"), dict) else {}
    declared = target_agent in (item.get("agent_compatible") or [])
    runtime_ready = (
        target_agent == "openclaw"
        and runtime.get("platform") == "openclaw"
        and readiness.get("ready") is True
    )

    if state in {"blocked", "broken", "unsupported"}:
        return {
            "compatible": False,
            "bonus": 0,
            "mode": "rejected",
            "state": state,
            "freshness_state": freshness_state,
        }
    if runtime_ready:
        return {
            "compatible": True,
            "bonus": 650,
            "mode": "runtime-ready",
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
    if declared or supports_target_agent(item, target_agent):
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


def candidate_text_blob(item: dict[str, Any]) -> str:
    parts = []
    for field in ["name", "qualified_name", "summary"]:
        value = item.get(field)
        if isinstance(value, str):
            parts.append(value.lower())
    for field in ["tags", "use_when", "capabilities"]:
        for value in item.get(field) or []:
            if isinstance(value, str):
                parts.append(value.lower())
    return " ".join(parts)


def memory_tokens(value: str) -> list[str]:
    tokens = []
    for token in tokenize(value):
        if len(token) < MEMORY_MIN_TOKEN_LENGTH:
            continue
        if token in MEMORY_TOKEN_STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def is_negative_experience(record: MemoryRecord) -> bool:
    if record.memory_type != "experience":
        return False
    return any(token in NEGATIVE_EXPERIENCE_TERMS for token in tokenize(record.memory))


def calculate_memory_signals(
    item: dict[str, Any],
    *,
    factors: dict[str, Any],
    records: list[MemoryRecord],
) -> dict[str, Any]:
    candidate_blob = candidate_text_blob(item)
    matched = []
    boostable = []
    for record in records:
        tokens = memory_tokens(record.memory)
        if not tokens:
            continue
        if any(token in candidate_blob for token in tokens):
            matched.append(record)
            if not is_negative_experience(record):
                boostable.append(record)

    boostable.sort(key=effective_memory_score, reverse=True)
    memory_types = []
    for record in boostable:
        memory_type = record.memory_type if isinstance(record.memory_type, str) else "generic"
        if memory_type not in memory_types:
            memory_types.append(memory_type)

    boost = 0
    if factors.get("compatibility"):
        for record in boostable:
            memory_type = record.memory_type if isinstance(record.memory_type, str) else "generic"
            quality_ratio = min(max(effective_memory_score(record), 0.25), 1.0)
            boost += int(round(MEMORY_TYPE_BOOSTS.get(memory_type, 8) * quality_ratio))
        boost = min(boost, MEMORY_MAX_BOOST)

    return {
        "matched_memory_count": len(matched),
        "applied_boost": boost,
        "memory_types": memory_types,
    }


def score_item(
    item: dict[str, Any],
    *,
    task_tokens: list[str],
    target_agent: str | None,
    default_registry: str,
) -> tuple[int, dict[str, Any]]:
    compatibility = compatibility_signal(item, target_agent=target_agent)
    private_preferred = item.get("source_registry") == default_registry
    matched_terms = match_strength(item, task_tokens)
    trust_score = TRUST_SCORES.get(item.get("trust_state") or "unknown", 0)
    maturity_score = MATURITY_SCORES.get(item.get("maturity") or "unknown", 0)
    quality_score = item.get("quality_score") if isinstance(item.get("quality_score"), int) else 0
    freshness = freshness_score(item.get("last_verified_at"))

    score = (
        (1000 if private_preferred else 0)
        + compatibility["bonus"]
        + (100 * matched_terms)
        + (30 * trust_score)
        + (20 * maturity_score)
        + quality_score
        + (10 * (1 if freshness > 0 else 0))
    )
    factors = {
        "private_registry": private_preferred,
        "compatibility": compatibility["compatible"],
        "compatibility_mode": compatibility["mode"],
        "compatibility_state": compatibility["state"],
        "compatibility_freshness": compatibility["freshness_state"],
        "match_strength": matched_terms,
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


def recommendation_reason(item: dict[str, Any], factors: dict[str, Any]) -> str:
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


__all__ = [
    "calculate_memory_signals",
    "compatibility_signal",
    "freshness_score",
    "match_strength",
    "recommendation_reason",
    "score_item",
    "tokenize",
]
