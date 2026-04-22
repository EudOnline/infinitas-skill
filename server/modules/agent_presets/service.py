from __future__ import annotations

import io
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from server.modules.agent_presets.models import AgentPresetSpec
from server.modules.agent_presets.schemas import (
    AgentPresetCreateRequest,
    AgentPresetDraftCreateRequest,
)
from server.modules.authoring import service as authoring_service
from server.modules.authoring.models import RegistryObject, Skill
from server.modules.authoring.schemas import SkillDraftCreateRequest
from server.modules.release.models import Artifact
from server.modules.release.storage import build_artifact_storage
from server.settings import get_settings


@dataclass
class AgentPresetRecord:
    spec: AgentPresetSpec
    registry_object: RegistryObject
    skill: Skill


def _dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stage_uploaded_bundle(*, filename: str, payload: dict) -> Artifact:
    settings = get_settings()
    storage = build_artifact_storage(settings.artifact_path)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        info = tarfile.TarInfo(filename)
        info.size = len(raw)
        archive.addfile(info, io.BytesIO(raw))
    stored = storage.put_bytes(
        buffer.getvalue(),
        public_path=f"draft-content/{Path(filename).name}.tar.gz",
    )
    return Artifact(
        release_id=None,
        kind="draft_content",
        storage_uri=stored.storage_uri,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
    )


def _serialize_preset_defaults(spec: AgentPresetSpec) -> dict:
    return {
        "kind": "agent_preset",
        "runtime_family": spec.runtime_family,
        "supported_memory_modes": json.loads(spec.supported_memory_modes_json or "[]"),
        "default_memory_mode": spec.default_memory_mode,
        "pinned_skill_dependencies": json.loads(spec.pinned_skill_dependencies_json or "[]"),
        "default_prompt": spec.default_prompt,
        "default_model": spec.default_model,
        "default_tools": json.loads(spec.default_tools_json or "[]"),
    }


def create_agent_preset(
    db: Session,
    *,
    namespace_id: int,
    actor_principal_id: int,
    payload: AgentPresetCreateRequest,
) -> AgentPresetRecord:
    registry_object = authoring_service.repository.create_registry_object(
        db,
        kind="agent_preset",
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
    spec = AgentPresetSpec(
        registry_object_id=registry_object.id,
        skill_id=skill.id,
        runtime_family=payload.runtime_family,
        supported_memory_modes_json=_dump_json(payload.supported_memory_modes),
        default_memory_mode=payload.default_memory_mode,
        pinned_skill_dependencies_json=_dump_json(payload.pinned_skill_dependencies),
    )
    db.add(spec)
    db.commit()
    db.refresh(spec)
    db.refresh(skill)
    db.refresh(registry_object)
    return AgentPresetRecord(spec=spec, registry_object=registry_object, skill=skill)


def get_agent_preset_or_404(db: Session, preset_id: int) -> AgentPresetRecord:
    spec = db.get(AgentPresetSpec, preset_id)
    if spec is None:
        raise authoring_service.NotFoundError("agent preset not found")
    skill = db.get(Skill, spec.skill_id)
    registry_object = db.get(RegistryObject, spec.registry_object_id)
    if skill is None or registry_object is None:
        raise authoring_service.NotFoundError("agent preset backing records not found")
    return AgentPresetRecord(spec=spec, registry_object=registry_object, skill=skill)


def create_agent_preset_draft(
    db: Session,
    *,
    preset_id: int,
    actor_principal_id: int,
    is_maintainer: bool,
    payload: AgentPresetDraftCreateRequest,
):
    record = get_agent_preset_or_404(db, preset_id)
    spec = record.spec

    artifact = _stage_uploaded_bundle(
        filename=f"{record.skill.slug}-preset.json",
        payload={
            "kind": "agent_preset",
            "slug": record.skill.slug,
            "prompt": payload.prompt,
            "model": payload.model,
            "tools": payload.tools,
            "runtime_family": spec.runtime_family,
            "supported_memory_modes": json.loads(spec.supported_memory_modes_json or "[]"),
            "default_memory_mode": spec.default_memory_mode,
            "pinned_skill_dependencies": json.loads(spec.pinned_skill_dependencies_json or "[]"),
        },
    )
    db.add(artifact)
    db.flush()

    draft = authoring_service.create_draft(
        db,
        skill_id=record.skill.id,
        actor_principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
        payload=SkillDraftCreateRequest(
            content_mode="uploaded_bundle",
            content_upload_token=str(artifact.id),
            metadata=_serialize_preset_defaults(spec),
        ),
    )
    spec.default_prompt = payload.prompt
    spec.default_model = payload.model
    spec.default_tools_json = _dump_json(payload.tools)
    db.add(spec)
    return draft


def seal_agent_preset_draft(
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
