from __future__ import annotations

from infinitas_skill.memory import build_memory_provider
from infinitas_skill.server.memory_curation import execute_memory_curation
from server.db import get_session_factory
from server.jobs import (
    append_job_log,
    claim_next_job,
    complete_job,
    fail_job,
    heartbeat_job,
    load_job_payload,
)
from server.models import Job
from server.modules.discovery.projections import refresh_projection_snapshot
from server.modules.memory.service import record_lifecycle_memory_event_best_effort
from server.modules.release.materializer import materialize_release
from server.modules.release.service import get_release_snapshot
from server.repo_ops import RepoOpError
from server.settings import get_settings


def _resolve_release_id(job: Job) -> int:
    if job.release_id is not None and int(job.release_id) > 0:
        return int(job.release_id)
    payload = load_job_payload(job)
    try:
        release_id = int(payload.get('release_id') or 0)
    except (TypeError, ValueError) as exc:
        raise RepoOpError('materialize_release job has invalid release_id payload') from exc
    if release_id <= 0:
        raise RepoOpError('materialize_release job is missing release_id payload')
    return release_id


def _process_materialize_release_job(session, job: Job, settings):
    release_id = _resolve_release_id(job)
    release, artifacts = materialize_release(
        session,
        release_id=release_id,
        artifact_root=settings.artifact_path,
        repo_root=settings.repo_path,
    )
    refresh_projection_snapshot(session, settings.artifact_path)
    append_job_log(job, f'materialized release {release.id} with {len(artifacts)} artifacts')
    return release


def _process_memory_curation_job(session, job: Job):
    payload = load_job_payload(job)
    action = str(payload.get("action") or "plan").strip().lower() or "plan"
    apply = bool(payload.get("apply"))
    try:
        limit = int(payload.get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50
    try:
        max_actions = int(payload.get("max_actions") or 20)
    except (TypeError, ValueError):
        max_actions = 20
    actor_ref = str(payload.get("actor_ref") or "system:memory-curation").strip()
    provider = build_memory_provider() if action == "prune" and apply else None
    summary = execute_memory_curation(
        session,
        action=action,
        apply=apply,
        provider=provider,
        limit=limit,
        max_actions=max_actions,
        actor_ref=actor_ref or "system:memory-curation",
    )
    execution = summary.get("execution") if isinstance(summary.get("execution"), dict) else {}
    append_job_log(
        job,
        "memory curation "
        f"action={summary.get('action')} apply={summary.get('apply')} "
        f"selected={execution.get('selected_candidates', 0)} "
        f"archived={execution.get('archived', 0)} "
        f"pruned={execution.get('pruned', 0)} "
        f"skipped={execution.get('skipped', 0)} "
        f"failed={execution.get('failed', 0)}",
    )
    return summary


def process_job(job_id: int):
    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise RepoOpError(f'job {job_id} not found')
        try:
            heartbeat_job(session, job, commit=False)
            if job.kind == 'materialize_release':
                release = _process_materialize_release_job(session, job, settings)
            elif job.kind == 'memory_curation':
                _process_memory_curation_job(session, job)
            else:
                raise RepoOpError(f'unsupported job kind: {job.kind}')
            complete_job(session, job, commit=False)
            session.commit()
            if job.kind == 'materialize_release':
                snapshot = get_release_snapshot(session, release.id)
                record_lifecycle_memory_event_best_effort(
                    session,
                    lifecycle_event="task.release.ready",
                    aggregate_type="release",
                    aggregate_id=str(release.id),
                    actor_ref=f"principal:{release.created_by_principal_id or 0}",
                    payload={
                        "release_id": str(release.id),
                        "skill_version_id": str(snapshot.skill_version.id),
                        "qualified_name": f"{snapshot.namespace.slug}/{snapshot.skill.slug}",
                        "version": snapshot.skill_version.version,
                    },
                )
        except Exception as exc:
            fail_job(session, job, error_message=str(exc), commit=False)
            session.commit()
            raise


def run_worker_loop(limit: int | None = None) -> int:
    processed = 0
    factory = get_session_factory()
    while limit is None or processed < limit:
        with factory() as session:
            job = claim_next_job(session)
            if job is None:
                break
            job_id = job.id
        process_job(job_id)
        processed += 1
    return processed
