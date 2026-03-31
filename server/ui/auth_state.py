from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from server.auth import maybe_get_current_access_context
from server.models import Principal, Release, Skill, SkillDraft, SkillVersion, User
from server.modules.access.authn import AccessContext
from server.ui.i18n import build_auth_redirect_url, resolve_language


def hydrate_auth_state(
    session_ui: dict[str, Any] | None,
    session_user: Any | None,
) -> dict[str, Any]:
    payload = dict(session_ui or {})
    if session_user is None:
        payload.pop("current_user", None)
        return payload
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


def require_skill_or_404(db: Session, skill_id: int) -> Skill:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return skill


def require_draft_bundle_or_404(db: Session, draft_id: int) -> tuple[SkillDraft, Skill]:
    draft = db.get(SkillDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")
    skill = db.get(Skill, draft.skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return draft, skill


def require_release_bundle_or_404(
    db: Session, release_id: int
) -> tuple[Release, SkillVersion, Skill]:
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="release not found")
    version = db.get(SkillVersion, release.skill_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="skill version not found")
    skill = db.get(Skill, version.skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return release, version, skill


__all__ = [
    "hydrate_auth_state",
    "is_owner",
    "principal_label",
    "require_draft_bundle_or_404",
    "require_lifecycle_actor",
    "require_release_bundle_or_404",
    "require_skill_or_404",
]
