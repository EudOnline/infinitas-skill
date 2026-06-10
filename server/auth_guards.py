"""Shared authentication guard helpers.

Consolidates the ``_require_principal`` / ``_require_actor`` /
``_require_library_actor`` pattern duplicated across API route files.
"""
from __future__ import annotations

from fastapi import HTTPException

from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.shared.actor import ActorRef


# ── Role-only checks ──────────────────────────────────────────────


def require_user_role(context: AccessContext, *, roles: frozenset[str] | set[str] | None = None) -> None:
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


def require_user_with_context(context: AccessContext, *, roles: frozenset[str] | set[str] | None = None) -> AccessContext:
    """Like :func:`require_user_role` but returns the *context* for chaining."""
    require_user_role(context, roles=roles)
    return context


def require_principal_context(context: AccessContext, *, roles: frozenset[str] | set[str] | None = None) -> AccessContext:
    """Validate user role *and* that a principal is attached. Returns *context*."""
    require_user_role(context, roles=roles)
    if context.principal is None:
        raise HTTPException(status_code=403, detail="principal required")
    return context


# ── Actor-returning guards ────────────────────────────────────────


def require_actor_ref(context: AccessContext, *, roles: frozenset[str] | set[str] | None = None) -> ActorRef:
    """Validate role + principal presence. Returns an :class:`ActorRef`."""
    require_user_role(context, roles=roles)
    if context.principal is None:
        raise HTTPException(status_code=403, detail="principal required")
    return ActorRef(
        principal=context.principal,
        is_maintainer=context.user.role == "maintainer",
    )


def build_actor_ref(context: AccessContext) -> ActorRef:
    """Build an :class:`ActorRef` from *context* without raising.

    ``is_maintainer`` is ``False`` when *context.user* is ``None``.
    """
    return ActorRef(
        principal=context.principal,  # type: ignore[arg-type]
        is_maintainer=context.user is not None and context.user.role == "maintainer",
    )


# ── Scope-aware guards ────────────────────────────────────────────


def require_authoring_principal(context: AccessContext) -> tuple[int, bool]:
    """Validate that *context* carries an authoring principal.

    Returns ``(principal_id, is_maintainer)``.

    Raises:
        HTTPException: 403 if no principal is attached or scopes are insufficient.
    """
    if context.principal is None:
        raise HTTPException(status_code=403, detail="authoring principal required")
    if not require_any_scope(context, {"api:user", "authoring:write", "skill:write"}):
        raise HTTPException(status_code=403, detail="insufficient scope")
    is_maintainer = bool(context.user is not None and context.user.role == "maintainer")
    return context.principal.id, is_maintainer
