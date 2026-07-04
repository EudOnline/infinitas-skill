from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from server.models import Principal, Skill, SkillVersion, utcnow
from server.modules.release.models import Artifact, Release


class ReleaseError(Exception):
    pass


class NotFoundError(ReleaseError, BaseNotFoundError):
    pass


class ConflictError(ReleaseError, BaseConflictError):
    pass


class ForbiddenError(ReleaseError, BaseForbiddenError):
    pass


@dataclass
class ReleaseSnapshot:
    release: Release
    skill_version: SkillVersion
    skill: Skill
    namespace: Principal
    manifest: dict


def get_skill_version_or_404(db: Session, version_id: int) -> SkillVersion:
    version = db.get(SkillVersion, version_id)
    if version is None:
        raise NotFoundError("skill version not found")
    return version


def get_release_or_404(db: Session, release_id: int) -> Release:
    release = db.get(Release, release_id)
    if release is None:
        raise NotFoundError("release not found")
    return release


def get_artifacts_for_release(db: Session, release_id: int) -> list[Artifact]:
    return list(
        db.scalars(
            select(Artifact)
            .where(Artifact.release_id == release_id)
            .order_by(Artifact.kind.asc(), Artifact.id.asc())
        ).all()
    )


def get_current_artifacts_for_release(db: Session, release: Release) -> list[Artifact]:
    artifact_ids = {
        int(artifact_id)
        for artifact_id in (
            release.bundle_artifact_id,
            release.manifest_artifact_id,
            release.provenance_artifact_id,
            release.signature_artifact_id,
        )
        if artifact_id is not None
    }
    if not artifact_ids:
        return []
    return list(
        db.scalars(
            select(Artifact)
            .where(Artifact.id.in_(sorted(artifact_ids)))
            .order_by(Artifact.kind.asc(), Artifact.id.asc())
        ).all()
    )


def _get_skill_or_404(db: Session, skill_id: int) -> Skill:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    return skill


def _get_namespace_or_404(db: Session, principal_id: int) -> Principal:
    namespace = db.get(Principal, principal_id)
    if namespace is None:
        raise NotFoundError("namespace principal not found")
    return namespace


def _version_manifest(skill_version: SkillVersion) -> dict:
    import json

    try:
        payload = json.loads(skill_version.sealed_manifest_json or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _version_has_source_snapshot(skill_version: SkillVersion) -> bool:
    manifest = _version_manifest(skill_version)
    content_mode = str(manifest.get("content_mode") or "").strip()
    return content_mode in {"external_ref", "uploaded_bundle"}


def assert_skill_owner(
    db: Session, skill: Skill, *, principal_id: int, is_maintainer: bool = False
) -> None:
    if is_maintainer:
        return
    if skill.namespace_id == principal_id:
        return
    from server.modules.access.models import Team, TeamMembership

    if (
        db.scalar(
            select(TeamMembership.id)
            .join(Team, Team.id == TeamMembership.team_id)
            .where(Team.principal_id == skill.namespace_id)
            .where(TeamMembership.user_id == principal_id)
        )
        is not None
    ):
        return
    raise ForbiddenError("release namespace access denied")


def create_or_get_release(
    db: Session,
    *,
    version_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
) -> tuple[Release, bool]:
    skill_version = get_skill_version_or_404(db, version_id)
    skill = _get_skill_or_404(db, skill_version.skill_id)
    assert_skill_owner(
        db,
        skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    existing = db.scalar(
        select(Release)
        .where(Release.skill_version_id == skill_version.id)
        .order_by(Release.id.desc())
        .with_for_update()
    )
    if existing is not None:
        return existing, False

    release = Release(
        skill_version_id=skill_version.id,
        skill_id=skill.id,
        state="preparing",
        format_version="1",
        created_by_principal_id=actor_principal_id,
    )
    db.add(release)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(Release)
            .where(Release.skill_version_id == skill_version.id)
            .order_by(Release.id.desc())
        )
        if existing is None:
            raise ConflictError("release already exists for skill version")
        return existing, False
    return release, True


def get_release_snapshot(db: Session, release_id: int) -> ReleaseSnapshot:
    release = get_release_or_404(db, release_id)
    skill_version = get_skill_version_or_404(db, release.skill_version_id)
    skill = _get_skill_or_404(db, skill_version.skill_id)
    namespace = _get_namespace_or_404(db, skill.namespace_id)
    manifest = _version_manifest(skill_version)
    return ReleaseSnapshot(
        release=release,
        skill_version=skill_version,
        skill=skill,
        namespace=namespace,
        manifest=manifest,
    )


def assert_release_owner(
    db: Session,
    release: Release,
    *,
    principal_id: int,
    is_maintainer: bool = False,
) -> None:
    snapshot = get_release_snapshot(db, release.id)
    assert_skill_owner(
        db,
        snapshot.skill,
        principal_id=principal_id,
        is_maintainer=is_maintainer,
    )


def upsert_artifact(
    db: Session,
    *,
    release_id: int,
    kind: str,
    storage_uri: str,
    sha256: str,
    size_bytes: int,
) -> Artifact:
    artifact = db.scalar(
        select(Artifact)
        .where(Artifact.release_id == release_id)
        .where(Artifact.kind == kind)
        .order_by(Artifact.id.desc())
    )
    if artifact is None:
        artifact = Artifact(
            release_id=release_id,
            kind=kind,
            storage_uri=storage_uri,
            sha256=sha256,
            size_bytes=size_bytes,
        )
        db.add(artifact)
        db.flush()
        return artifact

    artifact.storage_uri = storage_uri
    artifact.sha256 = sha256
    artifact.size_bytes = size_bytes
    db.add(artifact)
    db.flush()
    return artifact


def mark_release_ready(
    db: Session,
    *,
    release: Release,
    manifest_artifact_id: int,
    bundle_artifact_id: int,
    signature_artifact_id: int,
    provenance_artifact_id: int,
) -> Release:
    release.state = "ready"
    release.manifest_artifact_id = manifest_artifact_id
    release.bundle_artifact_id = bundle_artifact_id
    release.signature_artifact_id = signature_artifact_id
    release.provenance_artifact_id = provenance_artifact_id
    cast(Any, release).ready_at = utcnow()
    db.add(release)
    db.flush()
    return release
