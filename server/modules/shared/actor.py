"""Shared actor reference types.

Consolidates the ``ActorRef`` dataclass duplicated across access and shares
modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.modules.identity.models import Principal


@dataclass(frozen=True)
class ActorRef:
    principal: Principal
    is_maintainer: bool
    credential_id: int | None = None
    issued_for: str = ""
    request_id: str = ""


def actor_ref_label(actor: ActorRef) -> str:
    """Return a human-readable label for audit logging."""
    principal = f"principal:{actor.principal.slug}"
    if actor.credential_id is None:
        return principal
    return f"{principal};credential:{actor.credential_id}"


def actor_audit_payload(actor: ActorRef | None) -> dict[str, object]:
    if actor is None:
        return {}
    return {
        **({"credential_id": actor.credential_id} if actor.credential_id is not None else {}),
        **({"issued_for": actor.issued_for} if actor.issued_for else {}),
        **({"request_id": actor.request_id} if actor.request_id else {}),
    }
