from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import AccessGrant, Exposure
from server.modules.access.authn import AccessContext
from server.modules.access.service import grant_allows_release


def require_any_scope(context: AccessContext, allowed_scopes: set[str]) -> bool:
    return bool(context.scopes.intersection(allowed_scopes))


def can_access_release(db: Session, *, context: AccessContext, release_id: int) -> bool:
    credential = context.credential
    if credential.grant_id is not None:
        return grant_allows_release(db, grant_id=credential.grant_id, release_id=release_id)

    exposures = db.scalars(
        select(Exposure)
        .where(Exposure.release_id == release_id)
        .where(Exposure.state == "active")
        .where(Exposure.install_mode == "enabled")
    ).all()

    principal_id = context.principal.id if context.principal is not None else None
    for exposure in exposures:
        if exposure.audience_type == "public":
            return True
        if exposure.audience_type == "authenticated" and context.user is not None:
            return True
        if exposure.audience_type == "private" and principal_id is not None:
            if exposure.requested_by_principal_id == principal_id:
                return True
        if exposure.audience_type == "grant" and principal_id is not None:
            grants = db.scalars(
                select(AccessGrant)
                .where(AccessGrant.exposure_id == exposure.id)
                .where(AccessGrant.state == "active")
            ).all()
            for grant in grants:
                if grant.subject_ref == f"principal:{principal_id}":
                    return True
    return False
