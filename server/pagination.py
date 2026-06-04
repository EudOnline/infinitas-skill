"""Pagination utilities for API endpoints.

Provides standardized pagination support across all list endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


@dataclass
class PaginationParams:
    """Pagination parameters extracted from request.

    Attributes:
        skip: Number of items to skip (offset)
        limit: Maximum number of items to return
    """

    skip: int = 0
    limit: int = 20

    @classmethod
    def from_query(cls, skip: int = 0, limit: int = 20) -> "PaginationParams":
        """Create from FastAPI query parameters with validation."""
        # Clamp values to reasonable ranges
        skip = max(0, min(skip, 10000))
        limit = max(1, min(limit, 100))
        return cls(skip=skip, limit=limit)


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response structure.

    Type Parameters:
        T: The type of items in the results list

    Attributes:
        items: List of items for the current page
        total: Total number of items (across all pages)
        skip: Current offset
        limit: Current page size
        has_more: Whether there are more items after this page
    """

    items: list[T]
    total: int
    skip: int
    limit: int
    has_more: bool


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
