from __future__ import annotations

from sqlalchemy.orm import Session

from server.modules.access.authn import AccessContext
from server.modules.authoring.models import Skill


class ProductScopeForbidden(Exception):
    pass


def assert_product_token_skill_scope(
    db: Session,
    *,
    context: AccessContext,
    skill_id: int | None,
    allow_create: bool = False,
) -> None:
    credential = context.credential
    if credential.type != "product_token":
        return
    if credential.product_token_type != "publisher":  # noqa: S105
        raise ProductScopeForbidden("publisher token required")

    if credential.product_scope_type == "namespace":
        principal_id = context.principal.id if context.principal is not None else None
        if principal_id is None or credential.product_scope_id != principal_id:
            raise ProductScopeForbidden("publisher token namespace scope mismatch")
        if skill_id is None:
            if allow_create:
                return
            raise ProductScopeForbidden("skill scope required")
        skill = db.get(Skill, skill_id)
        if skill is None or skill.namespace_id != credential.product_scope_id:
            raise ProductScopeForbidden("publisher token namespace scope mismatch")
        return

    if skill_id is None:
        raise ProductScopeForbidden("object-scoped publisher tokens cannot create new objects")
    if credential.product_object_id != skill_id:
        raise ProductScopeForbidden("publisher token object scope mismatch")


__all__ = ["ProductScopeForbidden", "assert_product_token_skill_scope"]
