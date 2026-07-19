from __future__ import annotations

import time

from sqlalchemy.orm import Session

from server.db import session_scope
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
from server.modules.authoring.service import prune_expired_skill_contents
from server.modules.discovery.projections import refresh_projection_snapshot
from server.modules.jobs.models import Job
from server.modules.release.materializer import materialize_release
from server.modules.release.models import Release
from server.repo_ops import RepoOpError
from server.settings import Settings, get_settings

log = get_logger(__name__)


def _renew_job_lease(job_id: int) -> None:
    with session_scope() as heartbeat_session:
        job = heartbeat_session.get(Job, job_id)
        if job is None:
            raise RepoOpError(f"job {job_id} not found during lease renewal")
        if job.status != "running":
            raise RepoOpError(f"job {job_id} is no longer running during lease renewal")
        heartbeat_job(heartbeat_session, job)


def _resolve_release_id(job: Job) -> int:
    if job.release_id is not None and int(job.release_id) > 0:
        return int(job.release_id)
    payload = load_job_payload(job)
    try:
        release_id = int(payload.get("release_id") or 0)
    except (TypeError, ValueError) as exc:
        raise RepoOpError("materialize_release job has invalid release_id payload") from exc
    if release_id <= 0:
        raise RepoOpError("materialize_release job is missing release_id payload")
    return release_id


def _process_materialize_release_job(session: Session, job: Job, settings: Settings) -> Release:
    release_id = _resolve_release_id(job)
    release, artifacts = materialize_release(
        session,
        release_id=release_id,
        artifact_root=settings.artifact_path,
        repo_root=settings.repo_path,
        heartbeat=lambda: _renew_job_lease(job.id),
    )
    refresh_projection_snapshot(session, settings.artifact_path)
    append_job_log(job, f"materialized release {release.id} with {len(artifacts)} artifacts")
    return release


def _process_prune_skill_contents_job(session: Session, job: Job, settings: Settings) -> None:
    payload = load_job_payload(job)
    try:
        limit = int(payload.get("limit") or 1000)
    except (TypeError, ValueError) as exc:
        raise RepoOpError("prune_skill_contents job has invalid limit payload") from exc
    summary = prune_expired_skill_contents(
        session,
        artifact_root=settings.artifact_path,
        ttl_hours=settings.content_pending_ttl_hours,
        limit=max(1, min(limit, 10_000)),
    )
    append_job_log(job, f"pruned pending skill contents: {summary}")


def _is_retryable_error(exc: Exception) -> bool:
    """Determine if a job failure is transient and worth retrying."""
    message = str(exc).lower()
    # Network/git transient failures
    retryable_patterns = [
        "timeout",
        "timed out",
        "connection refused",
        "connection reset",
        "temporary failure",
        "could not resolve host",
        "name or service not known",
        "network is unreachable",
        "no space left on device",  # may resolve if other jobs free space
    ]
    return any(pattern in message for pattern in retryable_patterns)


def process_job(job_id: int) -> None:
    settings = get_settings()
    processing_error: Exception | None = None
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise RepoOpError(f"job {job_id} not found")
        try:
            _renew_job_lease(job.id)
            session.refresh(job)
            if job.kind == "materialize_release":
                _process_materialize_release_job(session, job, settings)
            elif job.kind == "prune_skill_contents":
                _process_prune_skill_contents_job(session, job, settings)
            else:
                raise RepoOpError(f"unsupported job kind: {job.kind}")
            complete_job(session, job)
            log.info(
                "job completed id=%d kind=%s",
                job.id,
                job.kind,
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
                retryable=retryable,
            )
            processing_error = exc
    if processing_error is not None:
        raise processing_error


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
    consecutive_empty = 0
    while limit is None or processed < limit:
        with session_scope() as session:
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
