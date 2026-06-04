from __future__ import annotations

import time

from infinitas_skill.memory import build_memory_provider
from infinitas_skill.server.memory_curation import execute_memory_curation
from server.db import get_session_factory
from server.jobs import (
    MAX_RETRY_ATTEMPTS,
    append_job_log,
    claim_next_job,
    complete_job,
    fail_job,
    heartbeat_job,
    load_job_payload,
)
from server.logging import get_logger
from server.models import Job
from server.modules.discovery.projections import refresh_projection_snapshot
from server.modules.memory.service import record_lifecycle_memory_event_best_effort
from server.modules.release.materializer import materialize_release
from server.modules.release.service import get_release_snapshot
from server.repo_ops import RepoOpError
from server.settings import get_settings

log = get_logger(__name__)


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


def _is_retryable_error(exc: Exception) -> bool:
    """Determine if a job failure is transient and worth retrying."""
    message = str(exc).lower()
    # Network/git transient failures
    retryable_patterns = [
        'timeout',
        'timed out',
        'connection refused',
        'connection reset',
        'temporary failure',
        'could not resolve host',
        'name or service not known',
        'network is unreachable',
        'no space left on device',  # may resolve if other jobs free space
    ]
    return any(pattern in message for pattern in retryable_patterns)


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
            log.info(
                "job completed id=%d kind=%s",
                job.id,
                job.kind,
            )
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
            retryable = _is_retryable_error(exc)
            if retryable and (job.attempt_count or 0) < MAX_RETRY_ATTEMPTS:
                log.warning(
                    "job failed (retryable) id=%d kind=%s attempt=%d error=%s",
                    job.id,
                    job.kind,
                    job.attempt_count,
                    exc,
                )
            else:
                log.error(
                    "job failed (permanent) id=%d kind=%s error=%s",
                    job.id,
                    job.kind,
                    exc,
                )
            fail_job(
                session,
                job,
                error_message=str(exc),
                commit=False,
                retryable=retryable,
            )
            session.commit()
            raise


def run_worker_loop(
    limit: int | None = None,
    *,
    poll_interval: float = 5.0,
    daemon: bool = False,
) -> int:
    """Process jobs from the queue.

    Parameters
    ----------
    limit:
        Maximum number of jobs to process. ``None`` means unlimited.
    poll_interval:
        Seconds to sleep between empty-queue checks when *daemon* is True.
    daemon:
        If True, keep polling even when the queue is empty (supervisor mode).
        If False (default), exit when no jobs are available (original batch mode).
    """
    processed = 0
    factory = get_session_factory()
    consecutive_empty = 0
    while limit is None or processed < limit:
        with factory() as session:
            job = claim_next_job(session)
            if job is None:
                if not daemon:
                    break
                consecutive_empty += 1
                if consecutive_empty == 1:
                    log.info("worker idle, polling every %.1fs", poll_interval)
                time.sleep(poll_interval)
                continue
            consecutive_empty = 0
            job_id = job.id
        try:
            process_job(job_id)
        except Exception as _job_exc:
            # process_job already marks the job failed/retried; log and continue
            log.debug("job %d error suppressed in loop: %s", job_id, _job_exc)
        processed += 1
    return processed
