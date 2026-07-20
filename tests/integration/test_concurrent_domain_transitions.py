from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select

from server.modules.audit.models import AuditEvent
from server.modules.authoring.models import Skill, SkillContent, SkillVersion
from server.modules.exposure.models import Exposure
from server.modules.exposure.schemas import ExposureCreateRequest
from server.modules.identity.models import Principal
from server.modules.release.models import Release
from server.modules.review.models import ReviewCase, ReviewDecision


def _seed_ready_release(db) -> tuple[int, int]:
    principal = Principal(kind="user", slug="concurrency-owner", display_name="Owner")
    db.add(principal)
    db.flush()
    skill = Skill(
        namespace_id=principal.id,
        slug="concurrency-skill",
        display_name="Concurrency Skill",
        default_visibility_profile="private",
        created_by_principal_id=principal.id,
    )
    db.add(skill)
    db.flush()
    content = SkillContent(
        public_id="cnt_concurrency",
        skill_id=skill.id,
        storage_uri="objects/sha256/concurrency",
        sha256="a" * 64,
        size_bytes=1,
        declared_version="1.0.0",
        created_by_principal_id=principal.id,
    )
    db.add(content)
    db.flush()
    version = SkillVersion(
        skill_id=skill.id,
        content_id=content.id,
        version="1.0.0",
        content_digest="sha256:" + "a" * 64,
        metadata_digest="sha256:" + "b" * 64,
        sealed_manifest_json="{}",
        created_by_principal_id=principal.id,
    )
    db.add(version)
    db.flush()
    release = Release(
        skill_version_id=version.id,
        skill_id=skill.id,
        state="ready",
        created_by_principal_id=principal.id,
    )
    db.add(release)
    db.commit()
    return release.id, principal.id


def test_concurrent_exposure_creation_allows_one_open_audience(db) -> None:
    from server.db import get_session_factory
    from server.modules.exposure import service

    release_id, principal_id = _seed_ready_release(db)
    barrier = Barrier(2)

    def create() -> str:
        session = get_session_factory()()
        try:
            barrier.wait()
            service.create_exposure(
                session,
                release_id=release_id,
                actor_principal_id=principal_id,
                payload=ExposureCreateRequest(audience_type="private"),
            )
            session.commit()
            return "created"
        except service.ConflictError:
            session.rollback()
            return "conflict"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: create(), range(2)))

    db.expire_all()
    exposures = list(
        db.scalars(
            select(Exposure)
            .where(Exposure.release_id == release_id)
            .where(Exposure.audience_type == "private")
        )
    )
    assert sorted(outcomes) == ["conflict", "created"]
    assert len(exposures) == 1


def test_concurrent_terminal_review_decisions_allow_one_winner(db) -> None:
    from server.db import get_session_factory
    from server.modules.review import service

    release_id, principal_id = _seed_ready_release(db)
    exposure = Exposure(
        release_id=release_id,
        audience_type="public",
        review_requirement="blocking",
        state="review_open",
        requested_by_principal_id=principal_id,
    )
    db.add(exposure)
    db.flush()
    review_case = service.open_review_case(
        db,
        exposure=exposure,
        actor_principal_id=principal_id,
        mode="blocking",
    )
    db.commit()
    review_case_id = review_case.id
    barrier = Barrier(2)

    def decide(decision: str) -> str:
        session = get_session_factory()()
        try:
            barrier.wait()
            service.record_decision(
                session,
                review_case_id=review_case_id,
                reviewer_principal_id=principal_id,
                decision=decision,
                note=decision,
                evidence={},
            )
            session.commit()
            return decision
        except service.ConflictError:
            session.rollback()
            return "conflict"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(decide, ("approve", "reject")))

    db.expire_all()
    final_case = db.get(ReviewCase, review_case_id)
    decisions = list(
        db.scalars(select(ReviewDecision).where(ReviewDecision.review_case_id == review_case_id))
    )
    assert outcomes.count("conflict") == 1
    assert len(decisions) == 1
    assert final_case is not None
    assert final_case.state == {"approve": "approved", "reject": "rejected"}[decisions[0].decision]


def test_blocking_review_approval_audits_exposure_activation(db) -> None:
    from server.modules.review import service

    release_id, principal_id = _seed_ready_release(db)
    exposure = Exposure(
        release_id=release_id,
        audience_type="public",
        review_requirement="blocking",
        state="review_open",
        requested_by_principal_id=principal_id,
    )
    db.add(exposure)
    db.flush()
    review_case = service.open_review_case(
        db,
        exposure=exposure,
        actor_principal_id=principal_id,
        mode="blocking",
    )
    db.commit()

    service.record_decision(
        db,
        review_case_id=review_case.id,
        reviewer_principal_id=principal_id,
        decision="approve",
        note="approved",
        evidence={},
    )
    db.commit()

    activation_events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "exposure")
            .where(AuditEvent.aggregate_id == str(exposure.id))
            .where(AuditEvent.event_type == "exposure.activated")
        )
    )
    assert exposure.state == "active"
    assert len(activation_events) == 1
    assert activation_events[0].actor_ref == f"principal:{principal_id}"
