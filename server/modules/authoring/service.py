from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy.orm import Session

from server.modules.authoring import repository
from server.modules.authoring.models import Skill, SkillDraft, SkillVersion
from server.modules.authoring.schemas import (
    SkillCreateRequest,
    SkillDraftCreateRequest,
    SkillDraftPatchRequest,
)
from server.modules.memory.service import record_lifecycle_memory_event_best_effort


class AuthoringError(Exception):
    pass


class NotFoundError(AuthoringError):
    pass


class ConflictError(AuthoringError):
    pass


class ForbiddenError(AuthoringError):
    pass


def canonical_metadata_json(metadata: dict | None) -> str:
    payload = metadata if isinstance(metadata, dict) else {}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def sha256_prefixed(raw: str) -> str:
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


_GIT_COMMIT_REF_PATTERN = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def is_sealable_content_ref(content_ref: str | None) -> bool:
    normalized = (content_ref or "").strip()
    if not normalized:
        return False
    if not normalized.startswith("git+"):
        return True

    _, separator, fragment = normalized.partition("#")
    if not separator:
        return False
    candidate = fragment.strip()
    return bool(_GIT_COMMIT_REF_PATTERN.fullmatch(candidate))


def create_skill(
    db: Session,
    *,
    namespace_id: int,
    actor_principal_id: int,
    payload: SkillCreateRequest,
) -> Skill:
    existing = repository.get_skill_by_namespace_and_slug(
        db,
        namespace_id=namespace_id,
        slug=payload.slug,
    )
    if existing is not None:
        raise ConflictError("skill slug already exists in namespace")
    skill = repository.create_skill(
        db,
        namespace_id=namespace_id,
        slug=payload.slug,
        display_name=payload.display_name,
        summary=payload.summary,
        default_visibility_profile=payload.default_visibility_profile,
        created_by_principal_id=actor_principal_id,
    )
    db.commit()
    db.refresh(skill)
    return skill


def get_skill_or_404(db: Session, skill_id: int) -> Skill:
    skill = repository.get_skill(db, skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    return skill


def assert_namespace_owner(
    skill: Skill, *, principal_id: int, is_maintainer: bool = False
) -> None:
    if is_maintainer:
        return
    if skill.namespace_id != principal_id:
        raise ForbiddenError("skill namespace access denied")


def create_draft(
    db: Session,
    *,
    skill_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    payload: SkillDraftCreateRequest,
) -> SkillDraft:
    skill = repository.get_skill(db, skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    assert_namespace_owner(
        skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    if payload.base_version_id is not None:
        base_version = repository.get_skill_version(db, payload.base_version_id)
        if base_version is None:
            raise NotFoundError("base skill version not found")
        if base_version.skill_id != skill.id:
            raise ConflictError("base skill version does not belong to skill")
    draft = repository.create_draft(
        db,
        skill_id=skill_id,
        base_version_id=payload.base_version_id,
        content_ref=payload.content_ref,
        metadata_json=canonical_metadata_json(payload.metadata),
        updated_by_principal_id=actor_principal_id,
    )
    db.commit()
    db.refresh(draft)
    record_lifecycle_memory_event_best_effort(
        db,
        lifecycle_event="task.authoring.create_draft",
        aggregate_type="skill_draft",
        aggregate_id=str(draft.id),
        actor_ref=f"principal:{actor_principal_id}",
        payload={
            "skill_id": str(skill.id),
            "skill_slug": skill.slug,
            "draft_state": draft.state,
        },
    )
    return draft


def patch_draft(
    db: Session,
    *,
    draft_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    payload: SkillDraftPatchRequest,
) -> SkillDraft:
    draft = repository.get_draft(db, draft_id)
    if draft is None:
        raise NotFoundError("draft not found")
    if draft.state != "open":
        raise ConflictError("sealed draft is immutable")
    skill = repository.get_skill(db, draft.skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    assert_namespace_owner(
        skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )

    if payload.content_ref is not None:
        draft.content_ref = payload.content_ref
    if payload.metadata is not None:
        draft.metadata_json = canonical_metadata_json(payload.metadata)
    draft.updated_by_principal_id = actor_principal_id
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def seal_draft(
    db: Session,
    *,
    draft_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    version: str,
) -> tuple[SkillDraft, SkillVersion]:
    draft = repository.get_draft(db, draft_id)
    if draft is None:
        raise NotFoundError("draft not found")
    if draft.state != "open":
        raise ConflictError("draft is already sealed")

    skill = repository.get_skill(db, draft.skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    assert_namespace_owner(
        skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    existing_version = repository.get_skill_version_by_skill_and_version(
        db,
        skill_id=skill.id,
        version=version,
    )
    if existing_version is not None:
        raise ConflictError("skill version already exists")

    frozen_content_ref = draft.content_ref or ""
    frozen_metadata = load_metadata(draft.metadata_json)
    if not is_sealable_content_ref(frozen_content_ref):
        raise ConflictError("draft content_ref must be an immutable snapshot before sealing")
    content_digest = sha256_prefixed(frozen_content_ref)
    metadata_digest = sha256_prefixed(canonical_metadata_json(frozen_metadata))

    skill_version = repository.create_skill_version(
        db,
        skill_id=draft.skill_id,
        version=version,
        content_digest=content_digest,
        metadata_digest=metadata_digest,
        created_from_draft_id=draft.id,
        created_by_principal_id=actor_principal_id,
    )
    draft.state = "sealed"
    draft.updated_by_principal_id = actor_principal_id
    db.add(draft)
    db.commit()
    db.refresh(draft)
    db.refresh(skill_version)
    record_lifecycle_memory_event_best_effort(
        db,
        lifecycle_event="task.authoring.seal_draft",
        aggregate_type="skill_draft",
        aggregate_id=str(draft.id),
        actor_ref=f"principal:{actor_principal_id}",
        payload={
            "skill_id": str(skill.id),
            "skill_slug": skill.slug,
            "version": skill_version.version,
            "skill_version_id": str(skill_version.id),
        },
    )
    return draft, skill_version
