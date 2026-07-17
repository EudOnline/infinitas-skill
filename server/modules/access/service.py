from __future__ import annotations

import json
import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.model_base import utcnow
from server.modules.access.models import AccessGrant
from server.modules.exposure.models import Exposure
from server.modules.identity.models import Credential
from server.modules.identity.service import encode_scopes, hash_token


def require_active_grant_exposure(db: Session, *, release_id: int) -> Exposure:
    """Return the active grant-type exposure for a release, or raise ValueError."""
    exposure = db.scalar(
        select(Exposure)
        .where(Exposure.release_id == release_id)
        .where(Exposure.audience_type == "grant")
        .where(Exposure.state == "active")
        .where(Exposure.install_mode == "enabled")
        .order_by(Exposure.id.desc())
    )
    if exposure is None:
        raise ValueError("active grant visibility required before issuing tokens")
    return exposure


def create_grant_token(
    db: Session,
    *,
    grant: AccessGrant,
    scopes: set[str] | None = None,
    principal_id: int | None = None,
    expires_at: datetime | None = None,
) -> tuple[str, Credential]:
    raw_token = f"grant_{secrets.token_urlsafe(24)}"
    credential = Credential(
        principal_id=principal_id,
        grant_id=grant.id,
        type="grant_token",
        hashed_secret=hash_token(raw_token),
        scopes_json=encode_scopes(scopes or {"artifact:download"}),
        resource_selector_json=json.dumps({"release_scope": "grant-bound"}, ensure_ascii=False),
        expires_at=expires_at,
        created_at=utcnow(),
    )
    db.add(credential)
    db.flush()
    return raw_token, credential


def grant_allows_release(db: Session, *, grant_id: int, release_id: int) -> bool:
    grant = db.get(AccessGrant, grant_id)
    if grant is None or grant.state != "active":
        return False
    exposure = db.get(Exposure, grant.exposure_id)
    if exposure is None:
        return False
    if exposure.audience_type != "grant":
        return False
    if exposure.state != "active" or exposure.install_mode != "enabled":
        return False
    return exposure.release_id == release_id
