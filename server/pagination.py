"""Pagination utilities for API endpoints.

Provides standardized pagination support across all list endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Query


@dataclass
class PaginationParams:
    """Pagination parameters extracted from request.

    Attributes:
        skip: Number of items to skip (offset)
        limit: Maximum number of items to return
    """

    skip: int = 0
    limit: int = 20


def create_paginated_response(
    items: list[Any],
    total: int,
    skip: int,
    limit: int,
) -> dict[str, Any]:
    """Create a paginated response dict.

    Args:
        items: List of items for the current page
        total: Total number of items across all pages
        skip: Current offset
        limit: Current page size

    Returns:
        Dictionary compatible with Pydantic response models
    """
    has_more = skip + limit < total
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": has_more,
    }


def query_pagination_params(
    skip: int = Query(default=0, ge=0, le=10000, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of items to return"),
) -> PaginationParams:
    """FastAPI dependency for pagination query parameters.

    Usage:
        @router.get("/api/items")
        def list_items(
            pagination: PaginationParams = Depends(query_pagination_params),
            db: Session = Depends(get_db),
        ):
            items = db.query(...).offset(pagination.skip).limit(pagination.limit).all()
            total = db.query(...).count()
            ...
    """
    return PaginationParams(skip=skip, limit=limit)
