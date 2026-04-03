from __future__ import annotations

from infinitas_skill.memory.context import (
    build_inspect_memory_query,
    build_recommendation_memory_query,
    effective_memory_score,
    render_memory_snippets,
)
from infinitas_skill.memory.contracts import MemoryRecord


def test_build_recommendation_memory_query_prefers_user_and_agent_scopes():
    query = build_recommendation_memory_query(
        task="install released skill into openclaw runtime",
        target_agent="openclaw",
        user_ref="maintainer",
    )
    assert query.scope_refs == ["user:maintainer", "agent:openclaw", "task:install"]
    assert query.provider_scope == {
        "user_ref": "maintainer",
        "agent_id": "openclaw",
        "task_ref": "install",
    }
    assert query.memory_types == ["user_preference", "task_context", "experience"]


def test_build_inspect_memory_query_includes_skill_and_deduped_scope_refs():
    query = build_inspect_memory_query(
        skill_ref="lvxiaoer/consume-infinitas-skill",
        target_agent="openclaw",
        user_ref="maintainer",
        extra_scope_refs=["agent:openclaw", "task:inspect", "user:maintainer"],
    )
    assert query.scope_refs == [
        "user:maintainer",
        "agent:openclaw",
        "skill:lvxiaoer/consume-infinitas-skill",
        "task:inspect",
    ]
    assert query.provider_scope == {
        "user_ref": "maintainer",
        "agent_id": "openclaw",
        "skill_ref": "lvxiaoer/consume-infinitas-skill",
        "task_ref": "inspect",
    }
    assert query.memory_types == ["task_context", "experience"]


def test_render_memory_snippets_is_deterministic_and_trimmed():
    records = [
        MemoryRecord(
            memory="Z item with lower score",
            memory_type="experience",
            score=0.2,
        ),
        MemoryRecord(
            memory="A item with highest score",
            memory_type="task_context",
            score=0.9,
        ),
        MemoryRecord(
            memory="A item with highest score",
            memory_type="task_context",
            score=0.9,
        ),
    ]
    snippets = render_memory_snippets(records, max_items=2, max_chars=18)
    assert snippets == ["task_context: A item with hig...", "experience: Z item with low..."]


def test_effective_memory_score_prefers_confident_reusable_memories():
    stronger = MemoryRecord(
        memory="Release-ready installs usually succeed for neptune workflows.",
        memory_type="experience",
        score=0.75,
        metadata={"confidence": 0.9, "ttl_seconds": 60 * 60 * 24 * 90},
    )
    weaker = MemoryRecord(
        memory="Temporary install note for neptune workflows.",
        memory_type="task_context",
        score=0.82,
        metadata={"confidence": 0.35, "ttl_seconds": 60 * 60 * 24 * 3},
    )
    assert effective_memory_score(stronger) > effective_memory_score(weaker)


def test_effective_memory_score_penalizes_short_lived_low_confidence_noise():
    durable = MemoryRecord(
        memory="Release-ready installs remain reliable for neptune workflows.",
        memory_type="experience",
        score=0.62,
        metadata={"confidence": 0.86, "ttl_seconds": 60 * 60 * 24 * 45},
    )
    noisy = MemoryRecord(
        memory="Temporary neptune note.",
        memory_type="task_context",
        score=0.65,
        metadata={"confidence": 0.08, "ttl_seconds": 60 * 15},
    )
    assert effective_memory_score(durable) > effective_memory_score(noisy)
