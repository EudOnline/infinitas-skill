from __future__ import annotations

from sqlalchemy.orm import Session

import server.modules.audit.service as audit_service
from server.modules.authoring.models import Skill, SkillContent, SkillVersion
from server.modules.shared.actor import ActorRef, actor_audit_payload, actor_ref_label


def _actor_label(actor: ActorRef | None, principal_id: int) -> str:
    return actor_ref_label(actor) if actor is not None else f"principal:{principal_id}"


def append_content_uploaded(
    db: Session,
    *,
    skill: Skill,
    content: SkillContent,
    principal_id: int,
    actor: ActorRef | None,
) -> None:
    audit_service.append_audit_event(
        db,
        aggregate_type="skill_content",
        aggregate_id=content.public_id,
        event_type="skill_content.uploaded",
        actor_ref=_actor_label(actor, principal_id),
        owner_principal_id=skill.namespace_id,
        payload={
            "object_id": skill.id,
            "content_id": content.public_id,
            "content_digest": f"sha256:{content.sha256}",
            **actor_audit_payload(actor),
        },
    )


def append_version_created(
    db: Session,
    *,
    skill: Skill,
    version: SkillVersion,
    principal_id: int,
    actor: ActorRef | None,
) -> None:
    audit_service.append_audit_event(
        db,
        aggregate_type="skill_version",
        aggregate_id=str(version.id),
        event_type="skill_version.created",
        actor_ref=_actor_label(actor, principal_id),
        owner_principal_id=skill.namespace_id,
        payload={
            "object_id": skill.id,
            "version_id": version.id,
            "version": version.version,
            **actor_audit_payload(actor),
        },
    )


__all__ = ["append_content_uploaded", "append_version_created"]
