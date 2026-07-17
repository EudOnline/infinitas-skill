from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

import server.modules.authoring.repository as repository
from server.exceptions_base import (
    ConflictError as BaseConflictError,
)
from server.exceptions_base import (
    ForbiddenError as BaseForbiddenError,
)
from server.exceptions_base import (
    NotFoundError as BaseNotFoundError,
)
from server.modules.authoring.content import canonicalize_skill_bundle
from server.modules.authoring.models import Skill, SkillContent, SkillVersion
from server.modules.authoring.schemas import SkillCreateRequest
from server.modules.release.storage import build_artifact_storage


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


def sha256_prefixed(raw: str) -> str:
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def canonical_manifest_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def get_skill_content_for_version(
    db: Session,
    *,
    skill_id: int,
    public_id: str,
) -> SkillContent:
    content = repository.get_skill_content_by_public_id(db, public_id)
    if content is None or content.skill_id != skill_id:
        raise NotFoundError("validated skill content not found")
    if content.state != "validated" or content.consumed_at is not None:
        raise ConflictError("skill content has already been consumed")
    return content


def _version_manifest(
    *,
    kind: str,
    content: SkillContent,
    metadata: dict,
) -> dict:
    return {
        "kind": kind,
        "content_mode": "uploaded_bundle",
        "content_id": content.public_id,
        "metadata": metadata,
    }


def upload_skill_content(
    db: Session,
    *,
    skill_id: int,
    actor_principal_id: int,
    is_maintainer: bool,
    raw_bundle: bytes,
    artifact_root: Path,
    repo_root: Path,
) -> SkillContent:
    skill = get_skill_or_404(db, skill_id)
    assert_namespace_owner(
        db,
        skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    canonical_bundle = canonicalize_skill_bundle(
        raw_bundle,
        skill_slug=skill.slug,
        repo_root=repo_root,
    )
    public_id = f"cnt_{secrets.token_urlsafe(18)}"
    stored = build_artifact_storage(artifact_root).put_bytes(
        canonical_bundle.data,
        public_path=f"version-content/{public_id}/skill.tar.gz",
    )
    return repository.create_skill_content(
        db,
        public_id=public_id,
        skill_id=skill.id,
        storage_uri=stored.storage_uri,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        declared_version=canonical_bundle.declared_version,
        created_by_principal_id=actor_principal_id,
    )


def create_skill_version_snapshot(
    db: Session,
    *,
    skill_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    version: str,
    content_public_id: str,
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

    content = get_skill_content_for_version(db, skill_id=skill.id, public_id=content_public_id)
    if content.declared_version != version:
        raise ConflictError("skill version does not match the version declared by uploaded content")
    frozen_metadata = metadata if isinstance(metadata, dict) else {}
    content_digest = f"sha256:{content.sha256}"
    metadata_digest = sha256_prefixed(canonical_metadata_json(frozen_metadata))
    version_manifest = _version_manifest(
        kind="skill_version_manifest",
        content=content,
        metadata=frozen_metadata,
    )

    if not repository.consume_skill_content(db, content.id):
        raise ConflictError("skill content has already been consumed")
    skill_version = repository.create_skill_version(
        db,
        skill_id=skill.id,
        content_id=content.id,
        version=version,
        content_digest=content_digest,
        metadata_digest=metadata_digest,
        sealed_manifest_json=canonical_manifest_json(version_manifest),
        created_by_principal_id=actor_principal_id,
    )
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
    db.flush()
    return skill


def get_skill_or_404(db: Session, skill_id: int) -> Skill:
    skill = repository.get_skill(db, skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    return skill


def list_skill_versions(
    db: Session,
    *,
    skill_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    limit: int | None = None,
    offset: int | None = None,
) -> list[SkillVersion]:
    skill = get_skill_or_404(db, skill_id)
    assert_namespace_owner(
        db,
        skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    return repository.list_skill_versions(db, skill_id=skill.id, limit=limit, offset=offset)


def _check_team_access(db: Session, namespace_id: int, principal_id: int) -> bool:
    from server.modules.identity.models import Team, TeamMembership

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
