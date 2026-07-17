from __future__ import annotations

from sqlalchemy.orm import Session

from server.modules.access.authn import AccessContext
from server.modules.library.projections import object_payload, type_details
from server.modules.library.queries import LibraryScope, load_library_scope
from server.modules.library.read_models import LibraryObjectDetailReadModel, LibraryObjectReadModel
from server.modules.library.releases import list_library_releases_from_scope


def list_library_objects(
    db: Session,
    *,
    actor: AccessContext,
    lang: str | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[list[LibraryObjectReadModel], int]:
    """List library objects with optional pagination.

    Returns:
        Tuple of (items, total_count).
    """
    scope, total = load_library_scope(db, actor=actor, skip=skip, limit=limit)
    items = [object_payload(scope, item, lang=lang) for item in scope.skills]
    return items, total


def get_library_object_detail(
    db: Session,
    *,
    actor: AccessContext,
    object_id: int,
    scope: LibraryScope | None = None,
) -> LibraryObjectDetailReadModel | None:
    if scope is None:
        scope, _total = load_library_scope(db, actor=actor)
    skill = next((item for item in scope.skills if item.id == object_id), None)
    if skill is None:
        return None
    return {
        "object": object_payload(scope, skill),
        "details": type_details(scope, skill),
        "releases": list_library_releases_from_scope(scope, skill_id=object_id),
    }
