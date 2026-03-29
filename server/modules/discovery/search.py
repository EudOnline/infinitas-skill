from __future__ import annotations

from server.modules.discovery.projections import DiscoveryProjection


def _score(query: str, entry: DiscoveryProjection) -> float:
    needle = (query or "").strip().lower()
    if not needle:
        return 1.0

    haystacks = [
        entry.name.lower(),
        entry.qualified_name.lower(),
        (entry.display_name or "").lower(),
        (entry.summary or "").lower(),
        entry.version.lower(),
    ]
    score = 0.0
    for index, haystack in enumerate(haystacks):
        if not haystack:
            continue
        if haystack == needle:
            score += 100.0 - index
        elif haystack.startswith(needle):
            score += 60.0 - index
        elif needle in haystack:
            score += 30.0 - index
    return score


def search_entries(
    entries: list[DiscoveryProjection],
    *,
    query: str,
    limit: int,
) -> list[DiscoveryProjection]:
    scored = []
    for entry in entries:
        score = _score(query, entry)
        if score <= 0:
            continue
        scored.append((score, entry))
    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].qualified_name,
            item[1].version,
        )
    )
    return [entry for _score_value, entry in scored[:limit]]
