from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.identity.auth import get_current_access_context
from server.modules.identity.guards import require_user_with_context as _require_library_actor
from server.modules.library.objects import get_library_object_detail, list_library_objects
from server.modules.library.read_models import LibraryObjectDetailReadModel
from server.modules.library.releases import list_library_releases
from server.modules.library.schemas import (
    LibraryObjectDetailView,
    LibraryObjectListView,
    LibraryReleaseListView,
)
from server.pagination import (
    PaginationParams,
    create_paginated_response,
    query_pagination_params,
)

router = APIRouter(prefix="/api/v1/library", tags=["library"])


@router.get("/", response_model=LibraryObjectListView)
def library_list(
    pagination: PaginationParams = Depends(query_pagination_params),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List library objects with pagination.

    Query Parameters:
        skip: Number of items to skip (default: 0, max: 10000)
        limit: Maximum items to return (default: 20, max: 100)
    """
    actor = _require_library_actor(context)
    items, total = list_library_objects(
        db, actor=actor, skip=pagination.skip, limit=pagination.limit
    )

    return create_paginated_response(
        items=items,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{object_id}", response_model=LibraryObjectDetailView)
def library_detail(
    object_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> LibraryObjectDetailReadModel:
    """Get detailed information about a library object.

    Returns the object overview, current release, visibility settings,
    token count, and share link count.

    Path Parameters:
        object_id: The library object ID
    """
    actor = _require_library_actor(context)
    detail = get_library_object_detail(db, actor=actor, object_id=object_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="object not found")
    return detail


@router.get("/{object_id}/releases", response_model=LibraryReleaseListView)
def library_releases(
    object_id: int,
    pagination: PaginationParams = Depends(query_pagination_params),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List releases for a library object with pagination.

    Path Parameters:
        object_id: The library object ID

    Query Parameters:
        skip: Number of items to skip (default: 0, max: 10000)
        limit: Maximum items to return (default: 20, max: 100)
    """
    actor = _require_library_actor(context)
    all_items = list_library_releases(db, actor=actor, object_id=object_id)
    if all_items is None:
        raise HTTPException(status_code=404, detail="object not found")

    # Releases are already scoped to a single object — apply in-memory pagination
    total = len(all_items)
    paginated_items = all_items[pagination.skip : pagination.skip + pagination.limit]

    return create_paginated_response(
        items=paginated_items,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )
