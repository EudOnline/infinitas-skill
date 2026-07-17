"""Identity authentication guard helpers.

Consolidates the ``_require_principal`` / ``_require_actor`` /
``_require_library_actor`` pattern duplicated across API route files.
"""

from __future__ import annotations

from fastapi import HTTPException

from server.modules.access.authn import AccessContext
from server.modules.shared.actor import ActorRef

# ── Role-only checks ──────────────────────────────────────────────


def require_user_role(
    context: AccessContext,
    *,
    roles: frozenset[str] | set[str] | None = None,
) -> None:
    """Validate that *context* carries an authenticated user with an allowed role.

    Raises:
        HTTPException: 403 on missing user or insufficient role.
    """
    if roles is None:
        roles = {"maintainer", "contributor"}
    if context.user is None:
        raise HTTPException(status_code=403, detail="user session required")
    if context.user.role not in roles:
        raise HTTPException(status_code=403, detail="insufficient role")


def require_user_with_context(
    context: AccessContext,
    *,
    roles: frozenset[str] | set[str] | None = None,
) -> AccessContext:
    """Like :func:`require_user_role` but returns the *context* for chaining."""
    require_user_role(context, roles=roles)
    return context


def require_actor_ref(
    context: AccessContext,
    *,
    roles: frozenset[str] | set[str] | None = None,
) -> ActorRef:
    """Validate role + principal presence. Returns an :class:`ActorRef`."""
    require_user_role(context, roles=roles)
    if context.user is None:
        raise HTTPException(status_code=403, detail="user session required")
    if context.principal is None:
        raise HTTPException(status_code=403, detail="principal required")
    return ActorRef(
        principal=context.principal,
        is_maintainer=context.user.role == "maintainer",
    )
