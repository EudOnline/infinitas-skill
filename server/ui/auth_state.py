from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from server.i18n import build_auth_redirect_url, resolve_language
from server.modules.access.authn import AccessContext
from server.modules.identity.auth import maybe_get_current_access_context
from server.modules.identity.models import Principal, User
from server.ui.queries import (
    get_release_bundle_or_404,
    get_skill_or_404,
)


def hydrate_auth_state(
    session_ui: dict[str, Any] | None,
    session_user: Any | None,
) -> dict[str, Any]:
    payload = dict(session_ui or {})
    if session_user is None:
        payload.pop("current_user", None)
        payload["has_auth_cookie_hint"] = False
        return payload
    payload["has_auth_cookie_hint"] = True
    payload["current_user"] = {
        "username": session_user.username,
        "role": session_user.role,
    }
    return payload


def principal_label(principal: Principal | None) -> str:
    if principal is None:
        return "-"
    return principal.display_name or principal.slug or f"principal-{principal.id}"


def is_owner(user: User, principal_id: int | None, resource_principal_id: int | None) -> bool:
    if user.role == "maintainer":
        return True
    if principal_id is None or resource_principal_id is None:
        return False
    return principal_id == resource_principal_id


def require_lifecycle_actor(
    request: Request,
    db: Session,
    *allowed_roles: str,
) -> AccessContext | RedirectResponse | dict[str, Any]:
    from server.ui.console import build_console_forbidden_context

    context = maybe_get_current_access_context(request, db)
    if context is None or context.user is None:
        return RedirectResponse(
            url=build_auth_redirect_url(request, resolve_language(request)),
            status_code=303,
        )
    if allowed_roles and context.user.role not in set(allowed_roles):
        return build_console_forbidden_context(
            request=request,
            user=context.user,
            allowed_roles=allowed_roles,
        )
    return context


__all__ = [
    "hydrate_auth_state",
    "is_owner",
    "principal_label",
    "require_lifecycle_actor",
    "get_skill_or_404",
    "get_release_bundle_or_404",
]
