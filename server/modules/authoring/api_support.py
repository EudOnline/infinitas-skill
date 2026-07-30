from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.access.credential_policy import (
    CredentialPolicyForbidden,
    assert_credential_mutation_allowed,
)
from server.modules.access.product_scope import (
    ProductScopeForbidden,
    assert_product_token_skill_scope,
)


def authoring_identity(context: AccessContext) -> tuple[int, bool]:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="authoring principal required")
    if not require_any_scope(
        context, {"api:user", "authoring:write", "skill:write", "registry:publish"}
    ):
        raise HTTPException(status_code=403, detail="insufficient scope")
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    return context.principal.id, is_maintainer


def authorize_skill(context: AccessContext, db: Session, skill_id: int, *, mutate: bool) -> None:
    try:
        assert_product_token_skill_scope(db, context=context, skill_id=skill_id)
        if mutate:
            assert_credential_mutation_allowed(
                db, credential=context.credential, object_kind="skill"
            )
    except (ProductScopeForbidden, CredentialPolicyForbidden) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


__all__ = ["authoring_identity", "authorize_skill"]
