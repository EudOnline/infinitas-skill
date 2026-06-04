"""Shared authentication guard helpers.

Consolidates the ``_require_principal`` / ``_require_actor`` pattern
for the publish router.
"""
from __future__ import annotations

from fastapi import HTTPException

from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope


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
