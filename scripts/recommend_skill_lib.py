#!/usr/bin/env python3
from pathlib import Path

from discovery_resolver_lib import load_discovery_index


TRUST_SCORES = {
    'verified': 3,
    'attested': 2,
    'installable': 1,
    'unknown': 0,
}

MATURITY_SCORES = {
    'stable': 3,
    'beta': 2,
    'experimental': 1,
    'unknown': 0,
}


def _tokenize(value: str | None) -> list[str]:
    if not isinstance(value, str):
        return []
    tokens = []
    for raw in value.lower().replace('/', ' ').replace('-', ' ').replace('_', ' ').split():
        cleaned = raw.strip()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _match_strength(item: dict, task_tokens: list[str]) -> int:
    if not task_tokens:
        return 0
    texts = []
    for field in ['name', 'qualified_name', 'summary']:
        value = item.get(field)
        if isinstance(value, str):
            texts.append(value.lower())
    for field in ['tags', 'use_when', 'capabilities']:
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
        digits = ''.join(ch for ch in value if ch.isdigit())
        return int(digits or '0')
    return 0


def _score_item(item: dict, *, task_tokens: list[str], target_agent: str | None, default_registry: str) -> tuple[int, dict]:
    compatibility = target_agent is None or target_agent in (item.get('agent_compatible') or [])
    private_preferred = item.get('source_registry') == default_registry
    match_strength = _match_strength(item, task_tokens)
    trust_score = TRUST_SCORES.get(item.get('trust_state') or 'unknown', 0)
    maturity_score = MATURITY_SCORES.get(item.get('maturity') or 'unknown', 0)
    quality_score = item.get('quality_score') if isinstance(item.get('quality_score'), int) else 0
    freshness = _freshness_score(item.get('last_verified_at'))

    score = (
        (1000 if private_preferred else 0)
        + (500 if compatibility else 0)
        + (100 * match_strength)
        + (30 * trust_score)
        + (20 * maturity_score)
        + quality_score
    )
    factors = {
        'private_registry': private_preferred,
        'compatibility': compatibility,
        'match_strength': match_strength,
        'trust': {
            'state': item.get('trust_state') or 'unknown',
            'score': trust_score,
        },
        'maturity': item.get('maturity') or 'unknown',
        'quality': quality_score,
        'verification_freshness': item.get('last_verified_at'),
        'verification_freshness_score': freshness,
    }
    return score, factors


def _recommendation_reason(item: dict, factors: dict) -> str:
    reasons = []
    if factors.get('private_registry'):
        reasons.append('private registry match')
    if factors.get('compatibility'):
        reasons.append('target-agent compatible')
    if factors.get('match_strength'):
        reasons.append(f"matched {factors.get('match_strength')} task terms")
    trust = (factors.get('trust') or {}).get('state')
    if trust:
        reasons.append(f'trust state {trust}')
    quality = factors.get('quality')
    if isinstance(quality, int) and quality > 0:
        reasons.append(f'quality score {quality}')
    return '; '.join(reasons) or 'deterministic fallback recommendation'


def recommend_skills(root: Path, task: str, target_agent: str | None = None, limit: int = 5) -> dict:
    root = Path(root).resolve()
    payload = load_discovery_index(root)
    default_registry = payload.get('default_registry')
    task_tokens = _tokenize(task)

    scored = []
    for item in payload.get('skills') or []:
        if not isinstance(item, dict):
            continue
        score, factors = _score_item(item, task_tokens=task_tokens, target_agent=target_agent, default_registry=default_registry)
        scored.append(
            (
                score,
                -(item.get('source_priority') or 0),
                item.get('qualified_name') or '',
                {
                    'name': item.get('name'),
                    'qualified_name': item.get('qualified_name'),
                    'publisher': item.get('publisher'),
                    'summary': item.get('summary'),
                    'source_registry': item.get('source_registry'),
                    'latest_version': item.get('latest_version'),
                    'trust_state': item.get('trust_state'),
                    'verified_support': item.get('verified_support') or {},
                    'install_requires_confirmation': item.get('install_requires_confirmation'),
                    'score': score,
                    'recommendation_reason': _recommendation_reason(item, factors),
                    'ranking_factors': factors,
                },
            )
        )

    scored.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))
    results = [entry[3] for entry in scored[: max(limit, 0)]]
    explanation = {}
    if results:
        winner = results[0]
        runner_up = results[1] if len(results) > 1 else None
        winner_reason = winner.get('recommendation_reason') or 'top deterministic recommendation'
        if runner_up:
            winner_reason = (
                f"{winner_reason}; outranked {runner_up.get('qualified_name')} via "
                f"private-first and deterministic ranking factors"
            )
        explanation = {
            'winner': winner.get('qualified_name'),
            'winner_reason': winner_reason,
            'runner_up': runner_up.get('qualified_name') if runner_up else None,
        }
    return {
        'ok': True,
        'task': task,
        'target_agent': target_agent,
        'results': results,
        'explanation': explanation,
    }
