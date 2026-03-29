from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.authz import can_access_release, require_any_scope
from server.modules.access.schemas import AccessIdentityView, ReleaseAccessCheckView

router = APIRouter(prefix="/api/v1/access", tags=["access"])


def _identity_view(context: AccessContext) -> AccessIdentityView:
    principal = context.principal
    user = context.user
    return AccessIdentityView(
        credential_id=context.credential.id,
        credential_type=context.credential.type,
        principal_id=principal.id if principal else None,
        principal_kind=principal.kind if principal else None,
        principal_slug=principal.slug if principal else None,
        user_id=user.id if user else None,
        username=user.username if user else None,
        scopes=sorted(context.scopes),
    )


@router.get("/me", response_model=AccessIdentityView)
def read_access_me(context: AccessContext = Depends(get_current_access_context)):
    return _identity_view(context)


@router.get("/releases/{release_id}/check", response_model=ReleaseAccessCheckView)
def check_release_access(
    release_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    scope_granted = require_any_scope(context, {"artifact:download", "release:read", "api:user"})
    if not scope_granted:
        raise HTTPException(status_code=403, detail="insufficient scope")
    if not can_access_release(db, context=context, release_id=release_id):
        raise HTTPException(status_code=403, detail="release access denied")
    return ReleaseAccessCheckView(
        ok=True,
        release_id=release_id,
        credential_type=context.credential.type,
        principal_id=context.principal.id if context.principal else None,
        scope_granted=scope_granted,
    )
