from __future__ import annotations

from infinitas_skill.memory.contracts import MemoryRecord
from infinitas_skill.memory.experience import build_experience_memory


def test_build_review_approval_experience_memory_is_traceable():
    memory = build_experience_memory(
        event_type="review.approved",
        aggregate_ref="review_case:12",
        payload={
            "qualified_name": "lvxiaoer/release-infinitas-skill",
            "audience_type": "public",
        },
    )
    assert memory.memory_type == "experience"
    assert memory.source_refs == ["review_case:12"]
    assert "public" in memory.content


def test_build_experience_memory_classifies_preference_and_task_context():
    preference = build_experience_memory(
        event_type="preference.updated",
        aggregate_ref="user:maintainer",
        payload={"preferred_agent": "codex"},
    )
    task = build_experience_memory(
        event_type="task.install",
        aggregate_ref="run:123",
        payload={"task": "install"},
    )
    assert preference.memory_type == "user_preference"
    assert task.memory_type == "task_context"


def test_build_experience_memory_uses_lifecycle_policy_defaults():
    release_ready = build_experience_memory(
        event_type="task.release.ready",
        aggregate_ref="release:5",
        payload={"qualified_name": "lvxiaoer/release-infinitas-skill"},
    )
    review_reject = build_experience_memory(
        event_type="task.review.reject",
        aggregate_ref="review_case:9",
        payload={"qualified_name": "lvxiaoer/release-infinitas-skill"},
    )
    create_draft = build_experience_memory(
        event_type="task.authoring.create_draft",
        aggregate_ref="skill_draft:3",
        payload={"skill_slug": "release-infinitas-skill"},
    )

    assert release_ready.memory_type == "experience"
    assert release_ready.confidence == 0.9
    assert release_ready.ttl_seconds == 60 * 60 * 24 * 90

    assert review_reject.memory_type == "experience"
    assert review_reject.confidence == 0.85
    assert review_reject.ttl_seconds == 60 * 60 * 24 * 21

    assert create_draft.memory_type == "task_context"
    assert create_draft.confidence == 0.45
    assert create_draft.ttl_seconds == 60 * 60 * 24 * 7


def test_build_experience_memory_explicit_values_override_policy_defaults():
    memory = build_experience_memory(
        event_type="task.release.ready",
        aggregate_ref="release:7",
        payload={"qualified_name": "lvxiaoer/release-infinitas-skill"},
        confidence=0.61,
        ttl_seconds=60,
    )
    assert memory.memory_type == "experience"
    assert memory.confidence == 0.61
    assert memory.ttl_seconds == 60


def test_build_experience_memory_filters_secrets_paths_and_grants():
    memory = build_experience_memory(
        event_type="review.approved",
        aggregate_ref="review_case:9",
        payload={
            "token": "secret-value",
            "grant_id": "grant_abc",
            "target_dir": "/tmp/private/path",
            "content_ref": "./private/path",
            "artifact": "catalog/foo.json",
            "audience_type": "public",
            "qualified_name": "lvxiaoer/release-infinitas-skill",
        },
    )
    assert "secret-value" not in memory.content
    assert "/tmp/private/path" not in memory.content
    assert "./private/path" not in memory.content
    assert "catalog/foo.json" not in memory.content
    assert "grant_abc" not in memory.content
    assert "audience_type=public" in memory.content
    assert "qualified_name=lvxiaoer/release-infinitas-skill" in memory.content


def test_build_experience_memory_keeps_provider_metadata():
    memory = build_experience_memory(
        event_type="review.approved",
        aggregate_ref="review_case:12",
        payload={"audience_type": "public"},
        provider_metadata={"source": "review-service", "trace_id": "abc"},
    )
    assert memory.provider_metadata == {"source": "review-service", "trace_id": "abc"}


def test_experience_memory_translates_cleanly_to_memory_record():
    experience = build_experience_memory(
        event_type="review.approved",
        aggregate_ref="review_case:12",
        payload={"audience_type": "public"},
        provider_metadata={"source": "review-service"},
    )
    record = experience.to_memory_record()
    assert isinstance(record, MemoryRecord)
    assert record.memory == experience.content
    assert record.memory_type == "experience"
    assert record.metadata["source_refs"] == ["review_case:12"]
    assert record.metadata["provider_metadata"] == {"source": "review-service"}
