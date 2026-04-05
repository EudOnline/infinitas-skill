from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Query, Session, sessionmaker

from server.jobs import claim_next_job, enqueue_job
from server.models import Base, Job, utcnow


def _configure_worker_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
    monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "disabled")
    monkeypatch.setenv("INFINITAS_MEMORY_CONTEXT_ENABLED", "0")
    monkeypatch.setenv("INFINITAS_MEMORY_WRITE_ENABLED", "0")


def test_job_lease_metadata_round_trips_through_sqlalchemy(tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'job-lease-roundtrip.db'}",
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )

    heartbeat_at = utcnow()
    lease_expires_at = heartbeat_at + timedelta(minutes=2)

    with session_factory() as session:
        job = Job(
            kind="materialize_release",
            status="running",
            payload_json="{}",
            heartbeat_at=heartbeat_at,
            lease_expires_at=lease_expires_at,
            attempt_count=2,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = int(job.id)

    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.heartbeat_at == heartbeat_at.replace(tzinfo=None)
        assert job.lease_expires_at == lease_expires_at.replace(tzinfo=None)
        assert job.attempt_count == 2

    engine.dispose()


def test_init_db_applies_job_lease_columns(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
    monkeypatch.setenv(
        "INFINITAS_SERVER_DATABASE_URL",
        f"sqlite:///{tmp_path / 'job-lease-migration.db'}",
    )
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
    monkeypatch.setenv("INFINITAS_SERVER_REPO_PATH", str(tmp_path / "repo"))

    from server.db import get_engine, init_db

    init_db()

    columns = {
        str(column["name"]): column
        for column in inspect(get_engine()).get_columns("jobs")
    }
    assert "heartbeat_at" in columns
    assert "lease_expires_at" in columns
    assert "attempt_count" in columns
    assert columns["attempt_count"]["nullable"] is False


def test_claim_next_job_is_atomic_under_concurrency(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'job-claim.db'}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )

    with session_factory() as session:
        enqueue_job(
            session,
            kind="memory_curation",
            payload={"action": "archive", "apply": False},
            requested_by=None,
        )

    start = Event()
    barrier = Barrier(2)
    original_first = Query.first

    def synchronized_first(self, *args, **kwargs):
        result = original_first(self, *args, **kwargs)
        descriptions = getattr(self, "column_descriptions", ())
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is Job and result is not None:
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(Query, "first", synchronized_first)

    def claim_once() -> int | None:
        start.wait(timeout=5)
        with session_factory() as session:
            job = claim_next_job(session)
            return None if job is None else int(job.id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(claim_once) for _ in range(2)]
        start.set()
        claimed_ids = [future.result(timeout=10) for future in futures]

    assert sorted(job_id for job_id in claimed_ids if job_id is not None) == [1]
    assert claimed_ids.count(None) == 1

    with session_factory() as session:
        job = session.get(Job, 1)
        assert job is not None
        assert job.status == "running"

    engine.dispose()


def test_claim_next_job_sets_lease_metadata_for_queued_work(tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'job-lease-claim.db'}",
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )

    with session_factory() as session:
        enqueue_job(
            session,
            kind="memory_curation",
            payload={"action": "archive", "apply": False},
            requested_by=None,
        )

    with session_factory() as session:
        job = claim_next_job(session)
        assert job is not None
        assert job.status == "running"
        assert job.started_at is not None
        assert job.heartbeat_at is not None
        assert job.lease_expires_at is not None
        assert job.lease_expires_at > job.heartbeat_at
        assert job.attempt_count == 1

    engine.dispose()


def test_claim_next_job_reclaims_stale_running_job_after_lease_expiry(tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'job-lease-reclaim.db'}",
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )

    with session_factory() as session:
        stale_claimed_at = utcnow() - timedelta(minutes=10)
        job = Job(
            kind="materialize_release",
            status="running",
            payload_json='{"release_id": 42}',
            release_id=42,
            started_at=stale_claimed_at,
            heartbeat_at=stale_claimed_at,
            lease_expires_at=stale_claimed_at + timedelta(minutes=1),
            attempt_count=1,
        )
        session.add(job)
        session.commit()
        job_id = int(job.id)

    with session_factory() as session:
        reclaimed = claim_next_job(session)
        assert reclaimed is not None
        assert reclaimed.id == job_id
        assert reclaimed.status == "running"
        assert reclaimed.started_at is not None
        assert reclaimed.heartbeat_at is not None
        assert reclaimed.lease_expires_at is not None
        assert reclaimed.lease_expires_at > reclaimed.heartbeat_at
        assert reclaimed.attempt_count == 2

    engine.dispose()


def test_process_job_refreshes_lease_before_work_and_clears_it_on_completion(
    monkeypatch, tmp_path
) -> None:
    _configure_worker_env(monkeypatch, tmp_path)

    from server import worker as worker_module
    from server.db import get_engine, get_session_factory

    Base.metadata.create_all(get_engine())
    session_factory = get_session_factory()

    stale_claimed_at = utcnow() - timedelta(minutes=10)
    old_heartbeat = stale_claimed_at.replace(tzinfo=None)
    observed: dict[str, object] = {}

    with session_factory() as session:
        job = Job(
            kind="memory_curation",
            status="running",
            payload_json='{"action":"archive","apply":false}',
            started_at=stale_claimed_at,
            heartbeat_at=stale_claimed_at,
            lease_expires_at=stale_claimed_at + timedelta(minutes=1),
            attempt_count=1,
        )
        session.add(job)
        session.commit()
        job_id = int(job.id)

    def fake_process_memory_curation_job(session, job):
        observed["heartbeat_at"] = job.heartbeat_at
        observed["lease_expires_at"] = job.lease_expires_at
        assert job.heartbeat_at is not None
        assert job.lease_expires_at is not None
        assert job.heartbeat_at.replace(tzinfo=None) > old_heartbeat
        assert job.lease_expires_at > job.heartbeat_at
        return {"ok": True}

    monkeypatch.setattr(
        worker_module,
        "_process_memory_curation_job",
        fake_process_memory_curation_job,
    )

    worker_module.process_job(job_id)

    assert observed["heartbeat_at"] is not None
    assert observed["lease_expires_at"] is not None

    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "completed"
        assert job.finished_at is not None
        assert job.heartbeat_at is None
        assert job.lease_expires_at is None


def test_process_job_clears_lease_metadata_when_work_fails(monkeypatch, tmp_path) -> None:
    _configure_worker_env(monkeypatch, tmp_path)

    from server import worker as worker_module
    from server.db import get_engine, get_session_factory

    Base.metadata.create_all(get_engine())
    session_factory = get_session_factory()

    stale_claimed_at = utcnow() - timedelta(minutes=10)
    old_heartbeat = stale_claimed_at.replace(tzinfo=None)

    with session_factory() as session:
        job = Job(
            kind="memory_curation",
            status="running",
            payload_json='{"action":"archive","apply":false}',
            started_at=stale_claimed_at,
            heartbeat_at=stale_claimed_at,
            lease_expires_at=stale_claimed_at + timedelta(minutes=1),
            attempt_count=1,
        )
        session.add(job)
        session.commit()
        job_id = int(job.id)

    def fake_process_memory_curation_job(session, job):
        assert job.heartbeat_at is not None
        assert job.lease_expires_at is not None
        assert job.heartbeat_at.replace(tzinfo=None) > old_heartbeat
        raise RuntimeError("boom")

    monkeypatch.setattr(
        worker_module,
        "_process_memory_curation_job",
        fake_process_memory_curation_job,
    )

    try:
        worker_module.process_job(job_id)
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected process_job to re-raise worker failures")

    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.finished_at is not None
        assert job.error_message == "boom"
        assert job.heartbeat_at is None
        assert job.lease_expires_at is None
