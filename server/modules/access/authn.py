from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from server.models import Credential, Principal, User
from server.modules.access import service


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
    normalized = service.normalize_token(token)
    if not normalized:
        return None

    credential = service.resolve_credential_by_token(db, normalized)
    if credential is None:
        return None

    principal = service.get_principal(db, credential.principal_id)
    user = service.get_user_for_principal(db, principal)
    return AccessContext(
        credential=credential,
        principal=principal,
        user=user,
        scopes=service.parse_scopes(credential.scopes_json),
    )
