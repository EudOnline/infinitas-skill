"""Shared actor reference types.

Consolidates the ``ActorRef`` dataclass duplicated across access and shares
modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.modules.access.models import Principal


@dataclass(frozen=True)
class ActorRef:
    principal: Principal
    is_maintainer: bool


def actor_ref_label(actor: ActorRef) -> str:
    """Return a human-readable label for audit logging."""
    return f"principal:{actor.principal.slug}"
