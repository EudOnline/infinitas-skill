from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

import server.modules.identity.service as identity_service
from server.modules.identity.models import Credential, Principal, User


@dataclass
class AccessContext:
    credential: Credential
    principal: Principal | None
    user: User | None
    scopes: set[str]


def resolve_access_context(
    db: Session,
    token: str | None,
) -> AccessContext | None:
    normalized = identity_service.normalize_token(token)
    if not normalized:
        return None

    credential = identity_service.resolve_credential_by_token(db, normalized)
    if credential is None:
        return None

    principal = identity_service.get_principal(db, credential.principal_id)
    user = identity_service.get_user_for_principal(db, principal)
    return AccessContext(
        credential=credential,
        principal=principal,
        user=user,
        scopes=identity_service.parse_scopes(credential.scopes_json),
    )
