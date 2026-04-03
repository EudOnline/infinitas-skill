from __future__ import annotations

from sqlalchemy.orm import Session

from server.jobs import enqueue_job, load_job_payload
from server.models import Job


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
    normalized_action = str(action or "").strip().lower() or "plan"
    payload = {
        "action": normalized_action,
        "apply": bool(apply),
        "limit": int(limit),
        "max_actions": int(max_actions),
        "actor_ref": str(actor_ref or "").strip() or "system:memory-curation",
    }
    return enqueue_job(
        db,
        kind="memory_curation",
        payload=payload,
        requested_by=None,
        note=note or f"memory curation {normalized_action}",
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


__all__ = ["build_memory_curation_job_summary", "enqueue_memory_curation_job"]
