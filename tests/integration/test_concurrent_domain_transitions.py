from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select

from server.modules.audit.models import AuditEvent
from server.modules.authoring.models import Skill, SkillChangeSet, SkillContent, SkillVersion
from server.modules.exposure.models import Exposure
from server.modules.exposure.schemas import ExposureCreateRequest
from server.modules.identity.models import Principal
from server.modules.release.models import Release
from server.modules.review.models import ReviewCase, ReviewDecision


def _seed_changeset_race(db) -> tuple[int, int, str, tuple[str, str]]:
    principal = Principal(kind="user", slug="changeset-owner", display_name="ChangeSet Owner")
    db.add(principal)
    db.flush()
    skill = Skill(
        namespace_id=principal.id,
        slug="changeset-race",
        display_name="ChangeSet Race",
        created_by_principal_id=principal.id,
    )
    db.add(skill)
    db.flush()
    base_content = SkillContent(
        public_id="cnt_changeset_base",
        skill_id=skill.id,
        storage_uri="objects/sha256/changeset-base",
        sha256="a" * 64,
        size_bytes=1,
        declared_version="1.0.0",
        state="consumed",
        created_by_principal_id=principal.id,
    )
    db.add(base_content)
    db.flush()
    base = SkillVersion(
        skill_id=skill.id,
        content_id=base_content.id,
        version="1.0.0",
        content_digest="sha256:" + "a" * 64,
        metadata_digest="sha256:" + "b" * 64,
        sealed_manifest_json="{}",
        created_by_principal_id=principal.id,
    )
    db.add(base)
    db.flush()
    skill.latest_content_digest = base.content_digest
    change_set_ids: list[str] = []
    for index, proposed in enumerate(("1.1.0", "1.2.0"), start=1):
        content = SkillContent(
            public_id=f"cnt_changeset_{index}",
            skill_id=skill.id,
            storage_uri=f"objects/sha256/changeset-{index}",
            sha256=str(index) * 64,
            size_bytes=1,
            declared_version=proposed,
            metadata_json="{}",
            created_by_principal_id=principal.id,
        )
        db.add(content)
        db.flush()
        change_set = SkillChangeSet(
            public_id=f"chg_changeset_{index}",
            skill_id=skill.id,
            base_version_id=base.id,
            candidate_content_id=content.id,
            proposed_version=proposed,
            state="submitted",
            created_by_principal_id=principal.id,
        )
        db.add(change_set)
        change_set_ids.append(change_set.public_id)
    db.commit()
    return skill.id, principal.id, base.content_digest, tuple(change_set_ids)


def test_concurrent_changeset_acceptance_has_one_cas_winner(db) -> None:
    from server.db import get_session_factory
    from server.modules.authoring import collaboration_service
    from server.modules.shared.actor import ActorRef

    skill_id, principal_id, base_digest, change_set_ids = _seed_changeset_race(db)
    barrier = Barrier(2)

    def accept(change_set_id: str) -> str:
        session = get_session_factory()()
        principal = session.get(Principal, principal_id)
        assert principal is not None
        try:
            barrier.wait()
            collaboration_service.accept_change_set(
                session,
                skill_id=skill_id,
                public_id=change_set_id,
                principal_id=principal_id,
                is_maintainer=False,
                expected_latest_digest=base_digest,
                pending_ttl_hours=24,
                actor=ActorRef(principal=principal, is_maintainer=False),
            )
            session.commit()
            return "accepted"
        except collaboration_service.authoring_service.ConflictError:
            session.rollback()
            return "conflict"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(accept, change_set_ids))

    db.expire_all()
    states = list(
        db.scalars(select(SkillChangeSet.state).where(SkillChangeSet.skill_id == skill_id)).all()
    )
    versions = list(db.scalars(select(SkillVersion).where(SkillVersion.skill_id == skill_id)))
    assert sorted(outcomes) == ["accepted", "conflict"]
    assert sorted(states) == ["accepted", "superseded"]
    assert len(versions) == 2


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


def _seed_version_race(db) -> tuple[int, int, tuple[str, str]]:
    principal = Principal(kind="user", slug="version-owner", display_name="Version Owner")
    db.add(principal)
    db.flush()
    skill = Skill(
        namespace_id=principal.id,
        slug="version-race",
        display_name="Version Race",
        created_by_principal_id=principal.id,
    )
    db.add(skill)
    db.flush()
    public_ids = ("cnt_version_race_a", "cnt_version_race_b")
    for index, public_id in enumerate(public_ids):
        db.add(
            SkillContent(
                public_id=public_id,
                skill_id=skill.id,
                storage_uri=f"objects/sha256/version-race-{index}",
                sha256=str(index + 1) * 64,
                size_bytes=1,
                declared_version="1.0.0",
                metadata_json="{}",
                created_by_principal_id=principal.id,
            )
        )
    db.commit()
    return skill.id, principal.id, public_ids


def test_concurrent_skill_version_creation_returns_one_conflict(db) -> None:
    from server.db import get_session_factory
    from server.modules.authoring import service

    skill_id, principal_id, content_ids = _seed_version_race(db)
    barrier = Barrier(2)

    def create(content_id: str) -> str:
        session = get_session_factory()()
        try:
            barrier.wait()
            service.create_skill_version_snapshot(
                session,
                skill_id=skill_id,
                actor_principal_id=principal_id,
                version="1.0.0",
                content_public_id=content_id,
                pending_ttl_hours=24,
            )
            session.commit()
            return "created"
        except service.ConflictError:
            session.rollback()
            return "conflict"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(create, content_ids))

    db.expire_all()
    versions = list(db.scalars(select(SkillVersion).where(SkillVersion.skill_id == skill_id)))
    contents = list(db.scalars(select(SkillContent).where(SkillContent.skill_id == skill_id)))
    assert sorted(outcomes) == ["conflict", "created"]
    assert len(versions) == 1
    assert sum(content.state == "consumed" for content in contents) == 1
    assert sum(content.state == "validated" for content in contents) == 1


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
