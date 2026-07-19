from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

import server.modules.authoring.repository as repository
from server.db import register_rollback_artifact_cleanup
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


class ContentQuotaError(AuthoringError):
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
    expires_before: datetime,
) -> SkillContent:
    content = repository.get_skill_content_by_public_id(db, public_id)
    if content is None or content.skill_id != skill_id:
        raise NotFoundError("validated skill content not found")
    if content.state != "validated" or content.consumed_at is not None:
        raise ConflictError("skill content has already been consumed")
    if _aware_utc(cast(datetime, content.created_at)) < expires_before:
        raise ConflictError("validated skill content has expired")
    return content


def _aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


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
    pending_ttl_hours: int,
    max_pending_per_skill: int,
    max_pending_bytes_per_principal: int,
) -> SkillContent:
    skill = get_skill_or_404(db, skill_id)
    assert_namespace_owner(
        db,
        skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    prune_expired_skill_contents(
        db,
        artifact_root=artifact_root,
        ttl_hours=pending_ttl_hours,
        limit=max_pending_per_skill,
        principal_id=actor_principal_id,
    )
    canonical_bundle = canonicalize_skill_bundle(
        raw_bundle,
        skill_slug=skill.slug,
        repo_root=repo_root,
    )
    _assert_pending_content_quota(
        db,
        skill_id=skill.id,
        principal_id=actor_principal_id,
        incoming_bytes=len(canonical_bundle.data),
        max_pending_per_skill=max_pending_per_skill,
        max_pending_bytes_per_principal=max_pending_bytes_per_principal,
    )
    public_id = f"cnt_{secrets.token_urlsafe(18)}"
    public_path = f"version-content/{public_id}/skill.tar.gz"
    expected_storage_uri = f"objects/sha256/{hashlib.sha256(canonical_bundle.data).hexdigest()}"
    object_was_referenced = repository.active_storage_uri_is_referenced(db, expected_storage_uri)
    storage = build_artifact_storage(artifact_root)
    stored = storage.put_bytes(
        canonical_bundle.data,
        public_path=public_path,
    )
    try:
        with db.begin_nested():
            content = repository.create_skill_content(
                db,
                public_id=public_id,
                skill_id=skill.id,
                storage_uri=stored.storage_uri,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                declared_version=canonical_bundle.declared_version,
                metadata_json=canonical_metadata_json(canonical_bundle.metadata),
                created_by_principal_id=actor_principal_id,
            )
    except Exception:
        storage.clear_public_path(f"version-content/{public_id}")
        if not object_was_referenced:
            storage.clear_public_path(stored.storage_uri)
        raise
    register_rollback_artifact_cleanup(
        db,
        root=artifact_root,
        path=f"version-content/{public_id}",
    )
    if not object_was_referenced:
        register_rollback_artifact_cleanup(db, root=artifact_root, path=stored.storage_uri)
    return content


def _assert_pending_content_quota(
    db: Session,
    *,
    skill_id: int,
    principal_id: int,
    incoming_bytes: int,
    max_pending_per_skill: int,
    max_pending_bytes_per_principal: int,
) -> None:
    skill_count, principal_bytes = repository.pending_content_usage(
        db,
        skill_id=skill_id,
        principal_id=principal_id,
    )
    if skill_count >= max_pending_per_skill:
        raise ContentQuotaError("skill pending content quota exceeded")
    if principal_bytes + incoming_bytes > max_pending_bytes_per_principal:
        raise ContentQuotaError("publisher pending content byte quota exceeded")


def prune_expired_skill_contents(
    db: Session,
    *,
    artifact_root: Path,
    ttl_hours: int,
    limit: int = 1000,
    principal_id: int | None = None,
) -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
    contents = repository.list_expired_skill_contents(
        db,
        cutoff=cutoff,
        limit=max(1, limit),
        principal_id=principal_id,
    )
    if not contents:
        return {"expired": 0, "public_paths_removed": 0, "objects_removed": 0}
    for content in contents:
        content.state = "expired"
        db.add(content)
    db.flush()

    storage = build_artifact_storage(artifact_root)
    public_removed = 0
    for content in contents:
        storage.clear_public_path(f"version-content/{content.public_id}")
        public_removed += 1
    object_removed = 0
    for storage_uri in {content.storage_uri for content in contents}:
        if not repository.active_storage_uri_is_referenced(db, storage_uri):
            storage.clear_public_path(storage_uri)
            object_removed += 1
    return {
        "expired": len(contents),
        "public_paths_removed": public_removed,
        "objects_removed": object_removed,
    }


def create_skill_version_snapshot(
    db: Session,
    *,
    skill_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    version: str,
    content_public_id: str,
    pending_ttl_hours: int,
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

    content = get_skill_content_for_version(
        db,
        skill_id=skill.id,
        public_id=content_public_id,
        expires_before=datetime.now(timezone.utc) - timedelta(hours=pending_ttl_hours),
    )
    if content.declared_version != version:
        raise ConflictError("skill version does not match the version declared by uploaded content")
    try:
        frozen_metadata = json.loads(content.metadata_json or "{}")
    except json.JSONDecodeError as exc:
        raise ConflictError("validated skill content metadata is invalid") from exc
    if not isinstance(frozen_metadata, dict):
        raise ConflictError("validated skill content metadata is invalid")
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
