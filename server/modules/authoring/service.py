from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.exceptions_base import (
    ConflictError as BaseConflictError,
)
from server.exceptions_base import (
    ForbiddenError as BaseForbiddenError,
)
from server.exceptions_base import (
    NotFoundError as BaseNotFoundError,
)
from server.modules.authoring import repository
from server.modules.authoring.models import Skill, SkillVersion
from server.modules.authoring.schemas import SkillCreateRequest
from server.modules.release.models import Artifact


class AuthoringError(Exception):
    pass


class NotFoundError(AuthoringError, BaseNotFoundError):
    pass


class ConflictError(AuthoringError, BaseConflictError):
    pass


class ForbiddenError(AuthoringError, BaseForbiddenError):
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
        raise ConflictError(
            "content_upload_token must reference a numeric uploaded artifact"
        ) from exc
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


def resolve_version_content(
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
        raise ConflictError("external_ref versions require content_ref")
    return normalized_mode, normalized_ref, None


def _content_digest_for_snapshot(
    db: Session,
    *,
    content_mode: str,
    content_ref: str,
    content_artifact_id: int | None,
) -> str:
    if content_mode == "uploaded_bundle":
        if content_artifact_id is None:
            raise ConflictError("uploaded_bundle version is missing content_artifact_id")
        artifact = repository.get_artifact(db, content_artifact_id)
        if artifact is None:
            raise NotFoundError("uploaded content artifact not found")
        return f"sha256:{artifact.sha256}"

    frozen_content_ref = content_ref or ""
    if not is_sealable_content_ref(frozen_content_ref):
        raise ConflictError("version content_ref must be an immutable snapshot")
    return sha256_prefixed(frozen_content_ref)


def _version_manifest(
    *,
    kind: str,
    content_mode: str,
    content_ref: str,
    content_artifact_id: int | None,
    metadata: dict,
) -> dict:
    return {
        "kind": kind,
        "content_mode": content_mode,
        "content_ref": content_ref,
        "content_artifact_id": content_artifact_id,
        "metadata": metadata,
    }


def create_skill_version_snapshot(
    db: Session,
    *,
    skill_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    version: str,
    content_mode: str | None = None,
    content_ref: str | None = None,
    content_upload_token: str | None = None,
    metadata: dict | None = None,
) -> SkillVersion:
    skill = repository.get_skill(db, skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    assert_namespace_owner(
        db,
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

    resolved_mode, resolved_ref, content_artifact_id = resolve_version_content(
        db,
        content_mode=content_mode,
        content_ref=content_ref,
        content_upload_token=content_upload_token,
    )
    frozen_metadata = metadata if isinstance(metadata, dict) else {}
    content_digest = _content_digest_for_snapshot(
        db,
        content_mode=resolved_mode,
        content_ref=resolved_ref,
        content_artifact_id=content_artifact_id,
    )
    metadata_digest = sha256_prefixed(canonical_metadata_json(frozen_metadata))
    version_manifest = _version_manifest(
        kind="skill_version_manifest",
        content_mode=resolved_mode,
        content_ref=resolved_ref,
        content_artifact_id=content_artifact_id,
        metadata=frozen_metadata,
    )

    skill_version = repository.create_skill_version(
        db,
        skill_id=skill.id,
        version=version,
        content_digest=content_digest,
        metadata_digest=metadata_digest,
        sealed_manifest_json=canonical_manifest_json(version_manifest),
        created_by_principal_id=actor_principal_id,
    )
    db.commit()
    db.refresh(skill_version)
    return skill_version


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


def _check_team_access(db: Session, namespace_id: int, principal_id: int) -> bool:
    from server.modules.access.models import Team, TeamMembership

    return (
        db.scalar(
            select(TeamMembership.id)
            .join(Team, Team.id == TeamMembership.team_id)
            .where(Team.principal_id == namespace_id)
            .where(TeamMembership.user_id == principal_id)
        )
        is not None
    )


def assert_namespace_owner(
    db: Session,
    skill: Skill,
    *,
    principal_id: int,
    is_maintainer: bool = False,
) -> None:
    if is_maintainer:
        return
    if skill.namespace_id == principal_id:
        return
    if _check_team_access(db, skill.namespace_id, principal_id):
        return
    raise ForbiddenError("skill namespace access denied")


