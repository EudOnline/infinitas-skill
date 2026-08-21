from __future__ import annotations

import hashlib
import hmac
import secrets
from base64 import urlsafe_b64encode

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.model_base import utcnow
from server.modules.identity.models import AgentInvitation
from server.settings import get_settings


class AgentEnrollmentError(Exception):
    pass


class AgentEnrollmentNotFound(AgentEnrollmentError):
    pass


class AgentEnrollmentConflict(AgentEnrollmentError):
    pass


class AgentEnrollmentExpired(AgentEnrollmentError):
    pass


def enrollment_token(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"


def enrollment_public_id(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(18)}"


def invitation_nonce_signature(value: str) -> str:
    digest = hmac.digest(
        get_settings().secret_key.encode("utf-8"),
        f"infinitas-agent-invitation-request-v1\0{value}".encode(),
        "sha256",
    )
    return urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def new_invitation_request_nonce() -> str:
    value = secrets.token_urlsafe(24)
    return f"ainr_{value}.{invitation_nonce_signature(value)}"


def validate_invitation_request_nonce(nonce: str) -> str:
    normalized = str(nonce or "").strip()
    prefix, separator, signature = normalized.partition(".")
    value = prefix.removeprefix("ainr_") if prefix.startswith("ainr_") else ""
    if not separator or len(value) != 32 or len(signature) != 43:
        raise AgentEnrollmentConflict("invalid invitation request nonce")
    if not hmac.compare_digest(signature, invitation_nonce_signature(value)):
        raise AgentEnrollmentConflict("invalid invitation request nonce")
    return normalized


def canonical_verifier(value: str) -> str:
    normalized = str(value or "").strip()
    if len(normalized) != 71 or not normalized.startswith("sha256:"):
        raise AgentEnrollmentConflict("invalid credential verifier")
    try:
        int(normalized[7:], 16)
    except ValueError as exc:
        raise AgentEnrollmentConflict("invalid credential verifier") from exc
    return normalized


def credential_fingerprint(verifier: str) -> str:
    canonical = canonical_verifier(verifier)
    payload = f"infinitas-agent-fingerprint-v1\0{canonical}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def active_invitation_for_reservation(db: Session, reservation_id: int) -> AgentInvitation | None:
    return db.scalar(
        select(AgentInvitation)
        .where(AgentInvitation.reservation_id == reservation_id)
        .where(AgentInvitation.state == "open")
        .where(AgentInvitation.expires_at > utcnow())
    )
