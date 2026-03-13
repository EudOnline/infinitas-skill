from __future__ import annotations

import json
from pathlib import Path

from server.artifact_ops import sync_catalog_artifacts
from server.db import get_session_factory
from server.jobs import append_job_log, claim_next_job, load_job_payload
from server.models import Job, Review, Submission, utcnow
from server.repo_ops import RepoOpError, commit_and_push, locked_repo, materialize_submission_skill, run_command
from server.settings import get_settings


def _latest_review(session, submission_id: int) -> Review | None:
    return session.query(Review).filter(Review.submission_id == submission_id).order_by(Review.id.desc()).first()


def _review_payload_for_submission(submission: Submission, review: Review | None) -> dict:
    requests = []
    if submission.review_requested_at is not None:
        requests.append(
            {
                'requested_at': submission.review_requested_at.isoformat().replace('+00:00', 'Z'),
                'requested_by': review.requested_by.username if review and review.requested_by else 'system',
                'note': review.note if review else 'Review requested by hosted control plane',
            }
        )

    entries = []
    if review and review.status in {'approved', 'rejected'}:
        entries.append(
            {
                'reviewer': review.reviewed_by.username if review.reviewed_by else 'system',
                'decision': review.status,
                'at': (review.updated_at or review.created_at).isoformat().replace('+00:00', 'Z'),
                'note': review.note or '',
            }
        )

    return {'version': 1, 'requests': requests, 'entries': entries}


def _submission_payload(submission: Submission) -> dict:
    try:
        payload = json.loads(submission.payload_json or '{}')
    except json.JSONDecodeError:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _repo_env(settings) -> dict:
    return {
        'INFINITAS_SERVER_REPO_PATH': str(settings.repo_path),
        'INFINITAS_SERVER_ARTIFACT_PATH': str(settings.artifact_path),
        'INFINITAS_SKILL_GIT_SIGNING_KEY': '',
        'INFINITAS_SKIP_RELEASE_TESTS': '1',
        'INFINITAS_SKIP_ATTESTATION_TESTS': '1',
        'INFINITAS_SKIP_DISTRIBUTION_TESTS': '1',
        'INFINITAS_SKIP_BOOTSTRAP_TESTS': '1',
        'INFINITAS_SKIP_AI_WRAPPER_TESTS': '1',
        'INFINITAS_SKIP_COMPAT_PIPELINE_TESTS': '1',
    }


def _process_validate_job(session, job: Job, settings):
    submission = session.get(Submission, job.submission_id)
    if submission is None:
        raise RepoOpError(f'submission {job.submission_id} not found for validation')
    payload = _submission_payload(submission)
    review = _latest_review(session, submission.id)
    review_payload = _review_payload_for_submission(submission, review)

    with locked_repo(settings.repo_lock_path):
        skill_dir = materialize_submission_skill(
            settings.repo_path,
            skill_name=submission.skill_name,
            payload=payload,
            review_payload=review_payload,
        )
        append_job_log(job, run_command(settings.repo_path, ['scripts/check-skill.sh', str(skill_dir)], env=_repo_env(settings)))
        for entry in commit_and_push(settings.repo_path, message=f'worker: validate submission {submission.skill_name}'):
            append_job_log(job, entry)
    submission.status = 'validated'
    submission.updated_at = utcnow()


def _process_promote_job(session, job: Job, settings):
    submission = session.get(Submission, job.submission_id)
    if submission is None:
        raise RepoOpError(f'submission {job.submission_id} not found for promotion')
    with locked_repo(settings.repo_lock_path):
        append_job_log(job, run_command(settings.repo_path, ['scripts/promote-skill.sh', submission.skill_name], env=_repo_env(settings)))
        for entry in commit_and_push(settings.repo_path, message=f'worker: promote submission {submission.skill_name}'):
            append_job_log(job, entry)
    submission.status = 'promoted'
    submission.updated_at = utcnow()


def _process_publish_job(session, job: Job, settings):
    submission = session.get(Submission, job.submission_id)
    if submission is None:
        raise RepoOpError(f'submission {job.submission_id} not found for publish')
    with locked_repo(settings.repo_lock_path):
        append_job_log(job, run_command(settings.repo_path, ['scripts/publish-skill.sh', submission.skill_name], env=_repo_env(settings)))
        sync_catalog_artifacts(settings.repo_path, settings.artifact_path)
        append_job_log(job, f'synced hosted artifacts to {settings.artifact_path}')
        for entry in commit_and_push(settings.repo_path, message=f'worker: publish submission {submission.skill_name}'):
            append_job_log(job, entry)
    submission.status = 'published'
    submission.updated_at = utcnow()


def process_job(job_id: int):
    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise RepoOpError(f'job {job_id} not found')
        try:
            if job.kind == 'validate_submission':
                _process_validate_job(session, job, settings)
            elif job.kind == 'promote_submission':
                _process_promote_job(session, job, settings)
            elif job.kind == 'publish_submission':
                _process_publish_job(session, job, settings)
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
