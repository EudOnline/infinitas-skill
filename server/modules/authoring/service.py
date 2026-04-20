from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.modules.authoring import repository
from server.modules.authoring.models import Skill, SkillDraft, SkillVersion
from server.modules.release.models import Artifact
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
_CONTENT_MODES = {"external_ref", "uploaded_bundle"}


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


def canonical_manifest_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_artifact_token(token: str | None) -> int | None:
    candidate = str(token or "").strip()
    if not candidate:
        return None
    try:
        artifact_id = int(candidate)
    except ValueError as exc:
        raise ConflictError("content_upload_token must reference a numeric uploaded artifact") from exc
    if artifact_id <= 0:
        raise ConflictError("content_upload_token must reference a positive artifact id")
    return artifact_id


def _resolve_uploaded_content_artifact(db: Session, token: str | None) -> Artifact:
    artifact_id = _parse_artifact_token(token)
    if artifact_id is None:
        raise ConflictError("uploaded_bundle drafts require content_upload_token")
    artifact = repository.get_artifact(db, artifact_id)
    if artifact is None:
        raise NotFoundError("uploaded content artifact not found")
    if artifact.release_id is not None:
        raise ConflictError("uploaded content artifact must be release-independent")
    return artifact


def resolve_draft_content(
    db: Session,
    *,
    content_mode: str | None,
    content_ref: str | None,
    content_upload_token: str | None,
) -> tuple[str, str, int | None]:
    normalized_mode = (content_mode or "").strip() or (
        "uploaded_bundle" if str(content_upload_token or "").strip() else "external_ref"
    )
    if normalized_mode not in _CONTENT_MODES:
        raise ConflictError(f"unsupported content_mode: {normalized_mode}")

    if normalized_mode == "uploaded_bundle":
        artifact = _resolve_uploaded_content_artifact(db, content_upload_token)
        return normalized_mode, "", artifact.id

    normalized_ref = (content_ref or "").strip()
    if not normalized_ref:
        raise ConflictError("external_ref drafts require content_ref")
    return normalized_mode, normalized_ref, None


def _content_digest_for_draft(db: Session, draft: SkillDraft) -> str:
    if draft.content_mode == "uploaded_bundle":
        if draft.content_artifact_id is None:
            raise ConflictError("uploaded_bundle draft is missing content_artifact_id")
        artifact = repository.get_artifact(db, draft.content_artifact_id)
        if artifact is None:
            raise NotFoundError("uploaded content artifact not found")
        return f"sha256:{artifact.sha256}"

    frozen_content_ref = draft.content_ref or ""
    if not is_sealable_content_ref(frozen_content_ref):
        raise ConflictError("draft content_ref must be an immutable snapshot before sealing")
    return sha256_prefixed(frozen_content_ref)


def _sealed_manifest_for_draft(draft: SkillDraft, metadata: dict) -> dict:
    return {
        "kind": "skill_draft_manifest",
        "content_mode": draft.content_mode,
        "content_ref": draft.content_ref,
        "content_artifact_id": draft.content_artifact_id,
        "metadata": metadata,
    }


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
        registry_object_id=repository.create_registry_object(
            db,
            kind="skill",
            namespace_id=namespace_id,
            slug=payload.slug,
            display_name=payload.display_name,
            summary=payload.summary,
            default_visibility_profile=payload.default_visibility_profile,
            created_by_principal_id=actor_principal_id,
        ).id,
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
    content_mode, content_ref, content_artifact_id = resolve_draft_content(
        db,
        content_mode=payload.content_mode,
        content_ref=payload.content_ref,
        content_upload_token=payload.content_upload_token,
    )
    draft = repository.create_draft(
        db,
        skill_id=skill_id,
        base_version_id=payload.base_version_id,
        content_mode=content_mode,
        content_ref=content_ref,
        content_artifact_id=content_artifact_id,
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

    if (
        payload.content_mode is not None
        or payload.content_ref is not None
        or payload.content_upload_token is not None
    ):
        content_mode, content_ref, content_artifact_id = resolve_draft_content(
            db,
            content_mode=payload.content_mode or draft.content_mode,
            content_ref=payload.content_ref if payload.content_ref is not None else draft.content_ref,
            content_upload_token=(
                payload.content_upload_token
                if payload.content_upload_token is not None
                else (str(draft.content_artifact_id) if draft.content_artifact_id is not None else None)
            ),
        )
        draft.content_mode = content_mode
        draft.content_ref = content_ref
        draft.content_artifact_id = content_artifact_id
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

    # Lock draft row to prevent concurrent seal race
    db.scalar(select(SkillDraft).where(SkillDraft.id == draft_id).with_for_update())

    skill = repository.get_skill(db, draft.skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    assert_namespace_owner(
        skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    existing_version = db.scalar(
        select(SkillVersion)
        .where(SkillVersion.skill_id == skill.id)
        .where(SkillVersion.version == version)
        .with_for_update()
    )
    if existing_version is not None:
        raise ConflictError("skill version already exists")

    frozen_metadata = load_metadata(draft.metadata_json)
    content_digest = _content_digest_for_draft(db, draft)
    metadata_digest = sha256_prefixed(canonical_metadata_json(frozen_metadata))
    sealed_manifest = _sealed_manifest_for_draft(draft, frozen_metadata)

    skill_version = repository.create_skill_version(
        db,
        skill_id=draft.skill_id,
        version=version,
        content_digest=content_digest,
        metadata_digest=metadata_digest,
        sealed_manifest_json=canonical_manifest_json(sealed_manifest),
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
