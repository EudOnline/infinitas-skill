from __future__ import annotations

from sqlalchemy.orm import Session

from server.jobs import enqueue_job, load_job_payload
from server.models import Job
from server.settings import get_settings


def resolve_memory_curation_job_options(
    *,
    action: str = "plan",
    apply: bool = False,
    limit: int = 50,
    max_actions: int = 20,
    actor_ref: str = "system:memory-curation",
    use_server_policy: bool = False,
) -> dict[str, object]:
    if use_server_policy:
        settings = get_settings()
        return {
            "action": settings.memory_curation_action,
            "apply": settings.memory_curation_apply,
            "limit": settings.memory_curation_limit,
            "max_actions": settings.memory_curation_max_actions,
            "actor_ref": settings.memory_curation_actor_ref,
        }
    normalized_action = str(action or "").strip().lower() or "plan"
    normalized_actor_ref = str(actor_ref or "").strip() or "system:memory-curation"
    normalized_limit = int(limit) if isinstance(limit, int) and limit > 0 else 50
    normalized_max_actions = (
        int(max_actions) if isinstance(max_actions, int) and max_actions > 0 else 20
    )
    return {
        "action": normalized_action,
        "apply": bool(apply),
        "limit": normalized_limit,
        "max_actions": normalized_max_actions,
        "actor_ref": normalized_actor_ref,
    }


def enqueue_memory_curation_job(
    db: Session,
    *,
    action: str,
    apply: bool,
    limit: int,
    max_actions: int,
    actor_ref: str,
    note: str = "",
    commit: bool = True,
) -> Job:
    payload = resolve_memory_curation_job_options(
        action=action,
        apply=apply,
        limit=limit,
        max_actions=max_actions,
        actor_ref=actor_ref,
    )
    return enqueue_job(
        db,
        kind="memory_curation",
        payload=payload,
        requested_by=None,
        note=note or f"memory curation {payload['action']}",
        commit=commit,
    )


def build_memory_curation_job_summary(job: Job) -> dict[str, object]:
    return {
        "id": int(job.id),
        "kind": str(job.kind),
        "status": str(job.status),
        "note": str(job.note or ""),
        "payload": load_job_payload(job),
    }


__all__ = [
    "build_memory_curation_job_summary",
    "enqueue_memory_curation_job",
    "resolve_memory_curation_job_options",
]
