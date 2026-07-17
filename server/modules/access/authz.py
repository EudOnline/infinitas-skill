from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.modules.access.authn import AccessContext
from server.modules.access.models import AccessGrant
from server.modules.access.service import grant_allows_release
from server.modules.exposure.models import Exposure


def require_any_scope(context: AccessContext, allowed_scopes: set[str]) -> bool:
    return bool(context.scopes.intersection(allowed_scopes))


def _build_active_grants_lookup(
    db: Session, *, exposures: Sequence[Exposure], principal_id: int | None
) -> dict[int, list[AccessGrant]]:
    """Bulk-fetch active AccessGrants for grant-type exposures.

    Returns a mapping of ``exposure_id → [AccessGrant, …]``.
    """
    active_grants: dict[int, list[AccessGrant]] = {}
    if principal_id is None:
        return active_grants

    grant_exposure_ids = [e.id for e in exposures if e.audience_type == "grant"]
    if not grant_exposure_ids:
        return active_grants

    rows = db.scalars(
        select(AccessGrant)
        .where(AccessGrant.exposure_id.in_(grant_exposure_ids))
        .where(AccessGrant.state == "active")
    ).all()
    for g in rows:
        active_grants.setdefault(g.exposure_id, []).append(g)
    return active_grants


def _release_is_accessible(
    *,
    exposures: list[Exposure],
    active_grants: dict[int, list[AccessGrant]],
    context: AccessContext,
    principal_id: int | None,
) -> bool:
    """Evaluate whether *any* exposure on a release grants access to *context*.

    This is the single source of truth for per-release access logic.
    """
    for exposure in exposures:
        audience = exposure.audience_type
        if audience == "public":
            return True
        if audience == "authenticated" and context.user is not None:
            return True
        if audience == "private" and principal_id is not None:
            if exposure.requested_by_principal_id == principal_id:
                return True
        if audience == "grant" and principal_id is not None:
            for grant in active_grants.get(exposure.id, []):
                if grant.subject_ref == f"principal:{principal_id}":
                    return True
    return False


def can_access_release(db: Session, *, context: AccessContext, release_id: int) -> bool:
    """Check whether *context* may access a single release.

    Thin wrapper around :func:`can_access_releases`.
    """
    return release_id in can_access_releases(db, context=context, release_ids=[release_id])


def can_access_releases(db: Session, *, context: AccessContext, release_ids: list[int]) -> set[int]:
    """Return the subset of *release_ids* that *context* can access.

    Uses exactly two queries regardless of input size:
    1. Bulk-fetch active exposures for all requested releases.
    2. Bulk-fetch active grants for grant-type exposures (if any).
    """
    if not release_ids:
        return set()

    credential = context.credential
    if credential.grant_id is not None:
        # Grant tokens are typically scoped to a single release;
        # fall back to per-item checks to keep logic identical.
        return {
            rid
            for rid in release_ids
            if grant_allows_release(db, grant_id=credential.grant_id, release_id=rid)
        }

    exposures = db.scalars(
        select(Exposure)
        .where(Exposure.release_id.in_(release_ids))
        .where(Exposure.state == "active")
        .where(Exposure.install_mode == "enabled")
    ).all()

    principal_id = context.principal.id if context.principal is not None else None
    active_grants = _build_active_grants_lookup(db, exposures=exposures, principal_id=principal_id)

    # Group exposures by release_id.
    exposures_by_release: dict[int, list[Exposure]] = {}
    for e in exposures:
        exposures_by_release.setdefault(e.release_id, []).append(e)

    accessible: set[int] = set()
    for rid in release_ids:
        if _release_is_accessible(
            exposures=exposures_by_release.get(rid, []),
            active_grants=active_grants,
            context=context,
            principal_id=principal_id,
        ):
            accessible.add(rid)

    return accessible
