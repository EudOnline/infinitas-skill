from __future__ import annotations

import json

from sqlalchemy.orm import Session

from server.modules.agent_codes.models import AgentCodeSpec
from server.modules.agent_codes.schemas import (
    AgentCodeCreateRequest,
    AgentCodeDraftCreateRequest,
)
from server.modules.authoring import service as authoring_service
from server.modules.authoring.models import RegistryObject, Skill
from server.modules.authoring.schemas import SkillDraftCreateRequest


class AgentCodeRecord:
    def __init__(self, *, spec: AgentCodeSpec, registry_object: RegistryObject, skill: Skill):
        self.spec = spec
        self.registry_object = registry_object
        self.skill = skill


def _dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def create_agent_code(
    db: Session,
    *,
    namespace_id: int,
    actor_principal_id: int,
    payload: AgentCodeCreateRequest,
) -> AgentCodeRecord:
    registry_object = authoring_service.repository.create_registry_object(
        db,
        kind="agent_code",
        namespace_id=namespace_id,
        slug=payload.slug,
        display_name=payload.display_name,
        summary=payload.summary,
        default_visibility_profile=None,
        created_by_principal_id=actor_principal_id,
    )
    skill = authoring_service.repository.create_skill(
        db,
        registry_object_id=registry_object.id,
        namespace_id=namespace_id,
        slug=payload.slug,
        display_name=payload.display_name,
        summary=payload.summary,
        default_visibility_profile=None,
        created_by_principal_id=actor_principal_id,
    )
    spec = AgentCodeSpec(
        registry_object_id=registry_object.id,
        skill_id=skill.id,
        runtime_family=payload.runtime_family,
        language=payload.language,
        entrypoint=payload.entrypoint,
    )
    db.add(spec)
    db.commit()
    db.refresh(spec)
    db.refresh(skill)
    db.refresh(registry_object)
    return AgentCodeRecord(spec=spec, registry_object=registry_object, skill=skill)


def get_agent_code_or_404(db: Session, code_id: int) -> AgentCodeRecord:
    spec = db.get(AgentCodeSpec, code_id)
    if spec is None:
        raise authoring_service.NotFoundError("agent code not found")
    skill = db.get(Skill, spec.skill_id)
    registry_object = db.get(RegistryObject, spec.registry_object_id)
    if skill is None or registry_object is None:
        raise authoring_service.NotFoundError("agent code backing records not found")
    return AgentCodeRecord(spec=spec, registry_object=registry_object, skill=skill)


def create_agent_code_draft(
    db: Session,
    *,
    code_id: int,
    actor_principal_id: int,
    is_maintainer: bool,
    payload: AgentCodeDraftCreateRequest,
):
    record = get_agent_code_or_404(db, code_id)
    spec = record.spec
    spec.external_source_json = _dump_json({"content_ref": payload.content_ref})
    db.add(spec)
    draft = authoring_service.create_draft(
        db,
        skill_id=record.skill.id,
        actor_principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
        payload=SkillDraftCreateRequest(
            content_mode="external_ref",
            content_ref=payload.content_ref,
            metadata={
                "kind": "agent_code",
                "runtime_family": spec.runtime_family,
                "language": spec.language,
                "entrypoint": spec.entrypoint,
            },
        ),
    )
    return draft


def seal_agent_code_draft(
    db: Session,
    *,
    draft_id: int,
    actor_principal_id: int,
    is_maintainer: bool,
    version: str,
):
    return authoring_service.seal_draft(
        db,
        draft_id=draft_id,
        actor_principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
        version=version,
    )
