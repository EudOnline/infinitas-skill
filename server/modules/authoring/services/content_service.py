"""Content and version management service.

Handles content resolution, digest calculation, and version snapshot creation.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from server.modules.authoring.repository import get_artifact
from server.modules.authoring.services.base import (
    ConflictError,
    NotFoundError,
    canonical_manifest_json,
    canonical_metadata_json,
    is_sealable_content_ref,
    is_valid_content_mode,
    sha256_prefixed,
)
from server.modules.release.models import Artifact

# ── Content Resolution ───────────────────────────────────────────────────────


def _parse_artifact_token(token: str | None) -> int | None:
    """Parse artifact upload token to get artifact ID.

    Args:
        token: Upload token string

    Returns:
        Artifact ID or None

    Raises:
        ConflictError: If token format is invalid
    """
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
    """Resolve uploaded content artifact from token.

    Args:
        db: Database session
        token: Upload token string

    Returns:
        Artifact object

    Raises:
        ConflictError: If token is invalid or artifact is already used
        NotFoundError: If artifact not found
    """
    artifact_id = _parse_artifact_token(token)
    if artifact_id is None:
        raise ConflictError("uploaded_bundle drafts require content_upload_token")
    artifact = get_artifact(db, artifact_id)
    if artifact is None:
        raise NotFoundError("uploaded content artifact not found")
    if artifact.release_id is not None:
        raise ConflictError("uploaded content artifact must be release-independent")
    return artifact


def resolve_content(
    db: Session,
    *,
    content_mode: str | None,
    content_ref: str | None,
    content_upload_token: str | None,
) -> tuple[str, str, int | None]:
    """Resolve content parameters into concrete mode, ref, and artifact.

    Args:
        db: Database session
        content_mode: Content mode (external_ref or uploaded_bundle)
        content_ref: Content reference (git+ URL or external ref)
        content_upload_token: Upload token for bundle uploads

    Returns:
        Tuple of (resolved_mode, resolved_ref, content_artifact_id)

    Raises:
        ConflictError: If content parameters are invalid
    """
    normalized_mode = (content_mode or "").strip() or (
        "uploaded_bundle" if str(content_upload_token or "").strip() else "external_ref"
    )
    if not is_valid_content_mode(normalized_mode):
        raise ConflictError(f"unsupported content_mode: {normalized_mode}")

    if normalized_mode == "uploaded_bundle":
        artifact = _resolve_uploaded_content_artifact(db, content_upload_token)
        return normalized_mode, "", artifact.id

    normalized_ref = (content_ref or "").strip()
    if not normalized_ref:
        raise ConflictError("external_ref versions require content_ref")
    return normalized_mode, normalized_ref, None


# ── Digest Calculation ───────────────────────────────────────────────────────


def calculate_content_digest(
    db: Session,
    *,
    content_mode: str,
    content_ref: str,
    content_artifact_id: int | None,
) -> str:
    """Calculate content digest for version or draft.

    Args:
        db: Database session
        content_mode: Content mode
        content_ref: Content reference
        content_artifact_id: Artifact ID for uploaded bundles

    Returns:
        Content digest with "sha256:" prefix

    Raises:
        ConflictError: If content is not sealable
        NotFoundError: If artifact not found
    """
    if content_mode == "uploaded_bundle":
        if content_artifact_id is None:
            raise ConflictError("uploaded_bundle version is missing content_artifact_id")
        artifact = get_artifact(db, content_artifact_id)
        if artifact is None:
            raise NotFoundError("uploaded content artifact not found")
        return f"sha256:{artifact.sha256}"

    frozen_content_ref = content_ref or ""
    if not is_sealable_content_ref(frozen_content_ref):
        raise ConflictError("version content_ref must be an immutable snapshot")
    return sha256_prefixed(frozen_content_ref)


def calculate_metadata_digest(metadata: dict) -> str:
    """Calculate metadata digest.

    Args:
        metadata: Metadata dictionary

    Returns:
        Metadata digest with "sha256:" prefix
    """
    return sha256_prefixed(canonical_metadata_json(metadata))


# ── Manifest Building ───────────────────────────────────────────────────────


def build_version_manifest(
    *,
    kind: str,
    content_mode: str,
    content_ref: str,
    content_artifact_id: int | None,
    metadata: dict,
) -> dict:
    """Build version manifest dictionary.

    Args:
        kind: Manifest kind (skill_version_manifest or skill_draft_manifest)
        content_mode: Content mode
        content_ref: Content reference
        content_artifact_id: Artifact ID for uploaded bundles
        metadata: Metadata dictionary

    Returns:
        Manifest dictionary
    """
    return {
        "kind": kind,
        "content_mode": content_mode,
        "content_ref": content_ref,
        "content_artifact_id": content_artifact_id,
        "metadata": metadata,
    }


def build_sealed_manifest(
    *,
    kind: str,
    content_mode: str,
    content_ref: str,
    content_artifact_id: int | None,
    metadata: dict,
) -> str:
    """Build and serialize sealed manifest.

    Args:
        kind: Manifest kind
        content_mode: Content mode
        content_ref: Content reference
        content_artifact_id: Artifact ID for uploaded bundles
        metadata: Metadata dictionary

    Returns:
        Serialized manifest JSON string
    """
    manifest = build_version_manifest(
        kind=kind,
        content_mode=content_mode,
        content_ref=content_ref,
        content_artifact_id=content_artifact_id,
        metadata=metadata,
    )
    return canonical_manifest_json(manifest)


__all__ = [
    "resolve_content",
    "calculate_content_digest",
    "calculate_metadata_digest",
    "build_version_manifest",
    "build_sealed_manifest",
]
