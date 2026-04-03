from __future__ import annotations

from dataclasses import dataclass

DAY_SECONDS = 60 * 60 * 24


@dataclass(frozen=True)
class MemoryPolicy:
    memory_type: str
    confidence: float
    ttl_seconds: int


def resolve_memory_policy(event_type: str) -> MemoryPolicy:
    normalized = str(event_type or "").strip().lower()

    if normalized.startswith("preference."):
        return MemoryPolicy(
            memory_type="user_preference",
            confidence=0.8,
            ttl_seconds=DAY_SECONDS * 60,
        )

    if normalized == "task.authoring.create_draft":
        return MemoryPolicy(
            memory_type="task_context",
            confidence=0.45,
            ttl_seconds=DAY_SECONDS * 7,
        )

    if normalized in {
        "task.authoring.seal_draft",
        "task.release.ready",
        "task.exposure.create",
        "task.exposure.activate",
        "task.review.approve",
        "task.review.reject",
    }:
        policy_map = {
            "task.authoring.seal_draft": MemoryPolicy(
                memory_type="experience",
                confidence=0.65,
                ttl_seconds=DAY_SECONDS * 30,
            ),
            "task.release.ready": MemoryPolicy(
                memory_type="experience",
                confidence=0.9,
                ttl_seconds=DAY_SECONDS * 90,
            ),
            "task.exposure.create": MemoryPolicy(
                memory_type="experience",
                confidence=0.6,
                ttl_seconds=DAY_SECONDS * 30,
            ),
            "task.exposure.activate": MemoryPolicy(
                memory_type="experience",
                confidence=0.75,
                ttl_seconds=DAY_SECONDS * 60,
            ),
            "task.review.approve": MemoryPolicy(
                memory_type="experience",
                confidence=0.8,
                ttl_seconds=DAY_SECONDS * 60,
            ),
            "task.review.reject": MemoryPolicy(
                memory_type="experience",
                confidence=0.85,
                ttl_seconds=DAY_SECONDS * 21,
            ),
        }
        return policy_map[normalized]

    if normalized.startswith("task."):
        return MemoryPolicy(
            memory_type="task_context",
            confidence=0.55,
            ttl_seconds=DAY_SECONDS * 14,
        )

    return MemoryPolicy(
        memory_type="experience",
        confidence=0.7,
        ttl_seconds=DAY_SECONDS * 30,
    )


__all__ = ["DAY_SECONDS", "MemoryPolicy", "resolve_memory_policy"]
