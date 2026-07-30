from __future__ import annotations

import json
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import server.modules.audit.service as audit_service
import server.modules.authoring.service as authoring_service
from server.modules.authoring.data_snapshot_schemas import DataSnapshotRegisterRequest
from server.modules.authoring.models import Skill, SkillDataSnapshot, SkillVersion
from server.modules.shared.actor import ActorRef, actor_audit_payload, actor_ref_label


def _authorize(db: Session, skill_id: int, principal_id: int, is_maintainer: bool) -> Skill:
    skill = authoring_service.get_skill_or_404(db, skill_id)
    authoring_service.assert_namespace_owner(
        db, skill, principal_id=principal_id, is_maintainer=is_maintainer
    )
    return skill


def get_snapshot(db: Session, *, skill_id: int, public_id: str) -> SkillDataSnapshot:
    snapshot = db.scalar(
        select(SkillDataSnapshot)
        .where(SkillDataSnapshot.skill_id == skill_id)
        .where(SkillDataSnapshot.public_id == public_id)
    )
    if snapshot is None:
        raise authoring_service.NotFoundError("skill data snapshot not found")
    return snapshot


def parent_public_id(db: Session, snapshot: SkillDataSnapshot) -> str | None:
    if snapshot.parent_snapshot_id is None:
        return None
    parent = db.get(SkillDataSnapshot, snapshot.parent_snapshot_id)
    return parent.public_id if parent is not None else None


def register_snapshot(
    db: Session,
    *,
    skill_id: int,
    principal_id: int,
    is_maintainer: bool,
    payload: DataSnapshotRegisterRequest,
    actor: ActorRef,
) -> SkillDataSnapshot:
    skill = _authorize(db, skill_id, principal_id, is_maintainer)
    version = db.get(SkillVersion, payload.skill_version_id)
    if version is None or version.skill_id != skill.id:
        raise authoring_service.NotFoundError("skill version not found")
    parent = None
    if payload.parent_snapshot_id is not None:
        parent = get_snapshot(db, skill_id=skill.id, public_id=payload.parent_snapshot_id)
        if parent.schema_version > payload.schema_version:
            raise authoring_service.ConflictError(
                "snapshot schema version cannot precede its parent"
            )
    snapshot = SkillDataSnapshot(
        public_id=f"dsp_{secrets.token_urlsafe(18)}",
        skill_id=skill.id,
        skill_version_id=version.id,
        parent_snapshot_id=parent.id if parent is not None else None,
        schema_version=payload.schema_version,
        encrypted_object_uri=payload.encrypted_object_uri,
        ciphertext_sha256=payload.ciphertext_sha256,
        ciphertext_size_bytes=payload.ciphertext_size_bytes,
        manifest_digest=payload.manifest_digest,
        encryption=payload.encryption,
        created_by_principal_id=principal_id,
        actor_metadata_json=json.dumps(actor_audit_payload(actor), sort_keys=True),
    )
    try:
        with db.begin_nested():
            db.add(snapshot)
            db.flush()
    except IntegrityError as exc:
        raise authoring_service.ConflictError("data snapshot already registered") from exc
    audit_service.append_audit_event(
        db,
        aggregate_type="skill_data_snapshot",
        aggregate_id=snapshot.public_id,
        event_type="skill_data_snapshot.registered",
        actor_ref=actor_ref_label(actor),
        owner_principal_id=skill.namespace_id,
        payload={
            "object_id": skill.id,
            "snapshot_id": snapshot.public_id,
            "skill_version_id": version.id,
            "ciphertext_sha256": snapshot.ciphertext_sha256,
            **actor_audit_payload(actor),
        },
    )
    return snapshot


def list_snapshots(
    db: Session, *, skill_id: int, principal_id: int, is_maintainer: bool
) -> list[SkillDataSnapshot]:
    _authorize(db, skill_id, principal_id, is_maintainer)
    return list(
        db.scalars(
            select(SkillDataSnapshot)
            .where(SkillDataSnapshot.skill_id == skill_id)
            .order_by(SkillDataSnapshot.created_at.desc(), SkillDataSnapshot.id.desc())
        ).all()
    )


__all__ = [
    "get_snapshot",
    "list_snapshots",
    "parent_public_id",
    "register_snapshot",
]
