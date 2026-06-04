"""Base service for authoring operations.

Provides common utilities and error handling for all authoring services.
"""
from __future__ import annotations

import json
import re

# ── Exceptions ───────────────────────────────────────────────────────────────


class AuthoringError(Exception):
    """Base exception for authoring service errors."""

    pass


class NotFoundError(AuthoringError):
    """Resource not found."""

    pass


class ConflictError(AuthoringError):
    """Resource conflict or duplicate."""

    pass


class ForbiddenError(AuthoringError):
    """Access denied."""

    pass


# ── Utility Functions ───────────────────────────────────────────────────────


def canonical_metadata_json(metadata: dict | None) -> str:
    """Convert metadata to canonical JSON string.

    Args:
        metadata: Metadata dictionary

    Returns:
        Canonical JSON string (sorted keys, compact)
    """
    payload = metadata if isinstance(metadata, dict) else {}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_metadata(raw: str | None) -> dict:
    """Load metadata from JSON string.

    Args:
        raw: JSON string or None

    Returns:
        Metadata dictionary (empty if invalid)
    """
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
    """Generate SHA256 hash with prefix.

    Args:
        raw: String to hash

    Returns:
        SHA256 hash with "sha256:" prefix
    """
    import hashlib

    return 'sha256:' + hashlib.sha256(raw.encode('utf-8')).hexdigest()


def canonical_manifest_json(payload: dict) -> str:
    """Convert manifest to canonical JSON string.

    Args:
        payload: Manifest dictionary

    Returns:
        Canonical JSON string (sorted keys, compact)
    """
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# ── Validation ───────────────────────────────────────────────────────────────


_GIT_COMMIT_REF_PATTERN = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_CONTENT_MODES = {"external_ref", "uploaded_bundle"}


def is_sealable_content_ref(content_ref: str | None) -> bool:
    """Check if content reference is an immutable snapshot.

    Args:
        content_ref: Content reference string

    Returns:
        True if the reference is sealable
    """
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


def is_valid_content_mode(content_mode: str) -> bool:
    """Check if content mode is valid.

    Args:
        content_mode: Content mode string

    Returns:
        True if the mode is valid
    """
    return content_mode in _CONTENT_MODES


__all__ = [
    "AuthoringError",
    "NotFoundError",
    "ConflictError",
    "ForbiddenError",
    "canonical_metadata_json",
    "load_metadata",
    "sha256_prefixed",
    "canonical_manifest_json",
    "is_sealable_content_ref",
    "is_valid_content_mode",
    "_CONTENT_MODES",
]
