from __future__ import annotations

import json
from server.db import get_session_factory
from server.jobs import append_job_log, claim_next_job, load_job_payload
from server.models import Job, utcnow
from server.modules.discovery.projections import refresh_projection_snapshot
from server.modules.release.materializer import materialize_release
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
    release, artifacts = materialize_release(session, release_id=release_id, artifact_root=settings.artifact_path)
    refresh_projection_snapshot(session, settings.artifact_path)
    append_job_log(job, f'materialized release {release.id} with {len(artifacts)} artifacts')


def process_job(job_id: int):
    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise RepoOpError(f'job {job_id} not found')
        try:
            if job.kind == 'materialize_release':
                _process_materialize_release_job(session, job, settings)
            else:
                raise RepoOpError(f'unsupported job kind: {job.kind}')
            job.status = 'completed'
            job.finished_at = utcnow()
            append_job_log(job, f'completed at {job.finished_at.isoformat().replace("+00:00", "Z")}')
            session.add(job)
            session.commit()
        except Exception as exc:
            job.status = 'failed'
            job.finished_at = utcnow()
            job.error_message = str(exc)
            append_job_log(job, f'ERROR: {exc}')
            session.add(job)
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
