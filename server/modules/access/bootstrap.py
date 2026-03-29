from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import User
from server.modules.access import service


def ensure_bootstrap_user_credentials(db: Session) -> int:
    users = db.scalars(select(User)).all()
    created_or_updated = 0
    for user in users:
        if not user.token:
            continue
        principal = service.ensure_user_principal(db, user)
        credential = service.ensure_personal_credential_for_user(
            db,
            user=user,
            principal=principal,
            raw_token=user.token,
        )
        if credential.id is not None:
            created_or_updated += 1
    db.commit()
    return created_or_updated
