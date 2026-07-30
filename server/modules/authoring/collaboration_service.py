from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import server.modules.audit.service as audit_service
import server.modules.authoring.service as authoring_service
from server.model_base import utcnow
from server.modules.authoring.collaboration_schemas import ChangeSetCreateRequest
from server.modules.authoring.models import Skill, SkillChangeSet, SkillContent, SkillVersion
from server.modules.shared.actor import ActorRef, actor_audit_payload, actor_ref_label


def _latest_version(db: Session, skill_id: int) -> SkillVersion | None:
    return authoring_service.repository.get_latest_skill_version(db, skill_id=skill_id)


def _change_set_or_404(db: Session, skill_id: int, public_id: str) -> SkillChangeSet:
    found = db.scalar(
        select(SkillChangeSet)
        .where(SkillChangeSet.skill_id == skill_id)
        .where(SkillChangeSet.public_id == public_id)
    )
    if found is None:
        raise authoring_service.NotFoundError("skill change set not found")
    return found


def content_public_id(db: Session, change_set: SkillChangeSet) -> str:
    content = db.get(SkillContent, change_set.candidate_content_id)
    if content is None:
        raise authoring_service.NotFoundError("change set content not found")
    return content.public_id


def _authorize(db: Session, skill_id: int, principal_id: int, is_maintainer: bool) -> Skill:
    skill = authoring_service.get_skill_or_404(db, skill_id)
    authoring_service.assert_namespace_owner(
        db, skill, principal_id=principal_id, is_maintainer=is_maintainer
    )
    return skill


def create_change_set(
    db: Session,
    *,
    skill_id: int,
    principal_id: int,
    is_maintainer: bool,
    payload: ChangeSetCreateRequest,
    pending_ttl_hours: int,
    actor: ActorRef,
) -> SkillChangeSet:
    skill = _authorize(db, skill_id, principal_id, is_maintainer)
    latest = _latest_version(db, skill.id)
    latest_id = latest.id if latest is not None else None
    if payload.base_version_id != latest_id:
        raise authoring_service.ConflictError("change set base must be the current latest version")
    if authoring_service.repository.get_skill_version_by_version(
        db, skill_id=skill.id, version=payload.proposed_version
    ):
        raise authoring_service.ConflictError("skill version already exists")
    content = authoring_service.get_skill_content_for_version(
        db,
        skill_id=skill.id,
        public_id=payload.content_id,
        expires_before=datetime.now(timezone.utc) - timedelta(hours=pending_ttl_hours),
    )
    if content.declared_version != payload.proposed_version:
        raise authoring_service.ConflictError("candidate content declares a different version")
    change_set = SkillChangeSet(
        public_id=f"chg_{secrets.token_urlsafe(18)}",
        skill_id=skill.id,
        base_version_id=payload.base_version_id,
        candidate_content_id=content.id,
        proposed_version=payload.proposed_version,
        created_by_principal_id=principal_id,
        actor_metadata_json=json.dumps(actor_audit_payload(actor), sort_keys=True),
    )
    try:
        with db.begin_nested():
            db.add(change_set)
            db.flush()
    except IntegrityError as exc:
        raise authoring_service.ConflictError(
            "candidate content already belongs to a change set"
        ) from exc
    _audit(db, skill, change_set, "skill_change_set.created", actor)
    return change_set


def list_change_sets(
    db: Session, *, skill_id: int, principal_id: int, is_maintainer: bool
) -> list[SkillChangeSet]:
    _authorize(db, skill_id, principal_id, is_maintainer)
    return list(
        db.scalars(
            select(SkillChangeSet)
            .where(SkillChangeSet.skill_id == skill_id)
            .order_by(SkillChangeSet.created_at.desc(), SkillChangeSet.id.desc())
        ).all()
    )


def get_change_set(
    db: Session, *, skill_id: int, public_id: str, principal_id: int, is_maintainer: bool
) -> SkillChangeSet:
    _authorize(db, skill_id, principal_id, is_maintainer)
    return _change_set_or_404(db, skill_id, public_id)


def submit_change_set(
    db: Session,
    *,
    skill_id: int,
    public_id: str,
    principal_id: int,
    is_maintainer: bool,
    actor: ActorRef,
) -> SkillChangeSet:
    skill = _authorize(db, skill_id, principal_id, is_maintainer)
    change_set = _change_set_or_404(db, skill_id, public_id)
    if change_set.state != "open":
        raise authoring_service.ConflictError("only open change sets can be submitted")
    change_set.state = "submitted"
    setattr(change_set, "submitted_at", utcnow())
    db.flush()
    _audit(db, skill, change_set, "skill_change_set.submitted", actor)
    return change_set


def reject_change_set(
    db: Session,
    *,
    skill_id: int,
    public_id: str,
    principal_id: int,
    is_maintainer: bool,
    actor: ActorRef,
) -> SkillChangeSet:
    skill = _authorize(db, skill_id, principal_id, is_maintainer)
    change_set = _change_set_or_404(db, skill_id, public_id)
    if change_set.state not in {"open", "submitted"}:
        raise authoring_service.ConflictError("only open or submitted change sets can be rejected")
    change_set.state = "rejected"
    setattr(change_set, "decided_at", utcnow())
    db.flush()
    _audit(db, skill, change_set, "skill_change_set.rejected", actor)
    return change_set


def _supersede_competitors(
    db: Session, *, skill: Skill, winner: SkillChangeSet, actor: ActorRef
) -> None:
    competitors = list(
        db.scalars(
            select(SkillChangeSet)
            .where(SkillChangeSet.skill_id == skill.id)
            .where(SkillChangeSet.id != winner.id)
            .where(SkillChangeSet.state.in_(("open", "submitted")))
            .with_for_update()
        ).all()
    )
    for change_set in competitors:
        change_set.state = "superseded"
        setattr(change_set, "decided_at", utcnow())
        _audit(db, skill, change_set, "skill_change_set.superseded", actor)


def accept_change_set(
    db: Session,
    *,
    skill_id: int,
    public_id: str,
    principal_id: int,
    is_maintainer: bool,
    expected_latest_digest: str | None,
    pending_ttl_hours: int,
    actor: ActorRef,
) -> tuple[SkillChangeSet, SkillVersion]:
    skill = _authorize(db, skill_id, principal_id, is_maintainer)
    change_set = _change_set_or_404(db, skill_id, public_id)
    if change_set.state != "submitted":
        raise authoring_service.ConflictError("only submitted change sets can be accepted")
    latest = _latest_version(db, skill.id)
    base_digest = latest.content_digest if latest is not None else None
    if change_set.base_version_id != (latest.id if latest else None):
        raise authoring_service.ConflictError("change set base is no longer current")
    if expected_latest_digest != base_digest:
        raise authoring_service.ConflictError(
            "expected latest digest does not match current version"
        )
    content = db.get(SkillContent, change_set.candidate_content_id)
    if content is None:
        raise authoring_service.NotFoundError("change set content not found")
    with db.begin_nested():
        version = authoring_service.create_skill_version_snapshot(
            db,
            skill_id=skill.id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            version=change_set.proposed_version,
            content_public_id=content.public_id,
            pending_ttl_hours=pending_ttl_hours,
            audit_actor=actor,
            expected_latest_digest=expected_latest_digest,
            enforce_expected_digest=True,
        )
        change_set.state = "accepted"
        setattr(change_set, "decided_at", utcnow())
        _supersede_competitors(db, skill=skill, winner=change_set, actor=actor)
    _audit(db, skill, change_set, "skill_change_set.accepted", actor)
    return change_set, version


def _audit(
    db: Session, skill: Skill, change_set: SkillChangeSet, event_type: str, actor: ActorRef
) -> None:
    audit_service.append_audit_event(
        db,
        aggregate_type="skill_change_set",
        aggregate_id=change_set.public_id,
        event_type=event_type,
        actor_ref=actor_ref_label(actor),
        owner_principal_id=skill.namespace_id,
        payload={
            "object_id": skill.id,
            "change_set_id": change_set.public_id,
            "state": change_set.state,
            **actor_audit_payload(actor),
        },
    )


__all__ = [
    "accept_change_set",
    "content_public_id",
    "create_change_set",
    "get_change_set",
    "list_change_sets",
    "reject_change_set",
    "submit_change_set",
]
