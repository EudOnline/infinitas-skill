"""Repository pattern base classes and interfaces.

This module provides the foundational Repository and UnitOfWork patterns
for data access, isolating the service layer from SQLAlchemy ORM details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    TypeVar,
)

from sqlalchemy import Select, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from server.exceptions import NotFoundError

T = TypeVar("T")
Id = TypeVar("Id", int, str)


class Repository(ABC, Generic[T, Id]):
    """Base repository interface for data access operations.

    Repositories encapsulate all database access logic and provide
    a clean interface for the service layer. They are responsible
    for CRUD operations, queries, and data mapping.

    Type Parameters:
        T: The entity model type (e.g., Skill, Release)
        Id: The ID type (typically int or str)
    """

    _session: Session

    def __init__(self, session: Session) -> None:
        """Initialize the repository with a database session.

        Args:
            session: SQLAlchemy ORM session
        """
        self._session = session

    @abstractmethod
    def get(self, id: Id) -> T | None:
        """Get an entity by ID.

        Args:
            id: The entity identifier

        Returns:
            The entity if found, None otherwise
        """

    @abstractmethod
    def get_or_404(self, id: Id) -> T:
        """Get an entity by ID or raise NotFoundError.

        Args:
            id: The entity identifier

        Returns:
            The entity

        Raises:
            NotFoundError: If the entity doesn't exist
        """

    @abstractmethod
    def list_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        order_by: InstrumentedAttribute | str | None = None,
    ) -> list[T]:
        """List entities with optional filtering, pagination, and sorting.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            filters: Optional field=value filters
            order_by: Optional field to order by

        Returns:
            List of entities
        """

    @abstractmethod
    def count(self, *, filters: dict[str, Any] | None = None) -> int:
        """Count entities with optional filtering.

        Args:
            filters: Optional field=value filters

        Returns:
            Number of matching entities
        """

    @abstractmethod
    def add(self, entity: T) -> None:
        """Add a new entity to the repository.

        Args:
            entity: The entity to add
        """

    @abstractmethod
    def update(self, entity: T) -> None:
        """Update an existing entity.

        Args:
            entity: The entity to update
        """

    @abstractmethod
    def delete(self, entity: T) -> None:
        """Delete an entity.

        Args:
            entity: The entity to delete
        """

    @abstractmethod
    def exists(self, id: Id) -> bool:
        """Check if an entity exists.

        Args:
            id: The entity identifier

        Returns:
            True if the entity exists, False otherwise
        """

    def _apply_filters(
        self, stmt: Select[tuple[T]], filters: dict[str, Any] | None
    ) -> Select[tuple[T]]:
        """Apply filters to a SQLAlchemy statement.

        Args:
            stmt: The base statement
            filters: Field=value filters

        Returns:
            The filtered statement
        """
        if not filters:
            return stmt

        model_type = self._get_model_type()
        for field_name, value in filters.items():
            if hasattr(model_type, field_name):
                stmt = stmt.where(getattr(model_type, field_name) == value)
        return stmt

    def _apply_order(
        self, stmt: Select[tuple[T]], order_by: InstrumentedAttribute | str | None
    ) -> Select[tuple[T]]:
        """Apply ordering to a SQLAlchemy statement.

        Args:
            stmt: The base statement
            order_by: Field to order by

        Returns:
            The ordered statement
        """
        if order_by is None:
            return stmt

        model_type = self._get_model_type()
        if isinstance(order_by, str):
            if hasattr(model_type, order_by):
                stmt = stmt.order_by(getattr(model_type, order_by))
        else:
            stmt = stmt.order_by(order_by)
        return stmt

    @abstractmethod
    def _get_model_type(self) -> type[T]:
        """Get the SQLAlchemy model type for this repository.

        Returns:
            The model class
        """


class SQLAlchemyRepository(Repository[T, Id], ABC):
    """SQLAlchemy-based repository implementation.

    Provides common CRUD operations using SQLAlchemy ORM.
    Subclasses should define the model type and any specialized queries.
    """

    def get(self, id: Id) -> T | None:
        """Get an entity by ID."""
        return self._session.get(self._get_model_type(), id)

    def get_or_404(self, id: Id) -> T:
        """Get an entity by ID or raise NotFoundError."""
        entity = self.get(id)
        if entity is None:
            raise NotFoundError(
                f"{self._get_model_type().__name__} with id {id} not found"
            )
        return entity

    def list_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        order_by: InstrumentedAttribute | str | None = None,
    ) -> list[T]:
        """List entities with optional filtering, pagination, and sorting."""
        model_type = self._get_model_type()
        stmt = select(model_type)

        stmt = self._apply_filters(stmt, filters)
        stmt = self._apply_order(stmt, order_by)

        stmt = stmt.offset(skip).limit(limit)
        return list(self._session.scalars(stmt).all())

    def count(self, *, filters: dict[str, Any] | None = None) -> int:
        """Count entities with optional filtering."""
        model_type = self._get_model_type()
        stmt = select(func.count()).select_from(model_type)

        stmt = self._apply_filters(stmt, filters)
        return self._session.scalar(stmt)

    def add(self, entity: T) -> None:
        """Add a new entity to the repository."""
        self._session.add(entity)

    def update(self, entity: T) -> None:
        """Update an existing entity."""
        self._session.add(entity)

    def delete(self, entity: T) -> None:
        """Delete an entity."""
        self._session.delete(entity)

    def exists(self, id: Id) -> bool:
        """Check if an entity exists."""
        return self.get(id) is not None

    def refresh(self, entity: T) -> T:
        """Refresh an entity from the database."""
        self._session.refresh(entity)
        return entity

    def flush(self) -> None:
        """Flush pending changes to the database."""
        self._session.flush()


class QueryBuilder(Generic[T]):
    """Helper for building complex queries dynamically.

    Provides a fluent interface for constructing SQLAlchemy queries
    with optional joins, filters, and ordering.
    """

    def __init__(
        self,
        session: Session,
        model_type: type[T],
        base_stmt: Select[tuple[T]] | None = None,
    ) -> None:
        """Initialize the query builder.

        Args:
            session: Database session
            model_type: The model class
            base_stmt: Optional base statement to build from
        """
        self._session = session
        self._model_type = model_type
        self._stmt = base_stmt if base_stmt is not None else select(model_type)
        self._eager_load_paths: list[tuple[InstrumentedAttribute, ...]] = []
        self._filter_conditions: list[Any] = []

    def filter(self, *conditions: Any) -> QueryBuilder[T]:
        """Add filter conditions.

        Args:
            *conditions: SQLAlchemy filter expressions

        Returns:
            Self for chaining
        """
        self._filter_conditions.extend(conditions)
        return self

    def join(
        self,
        *attrs: InstrumentedAttribute,
        inner: bool = True,
    ) -> QueryBuilder[T]:
        """Add joins to the query.

        Args:
            *attrs: Attributes to join
            inner: Use INNER JOIN (True) or LEFT OUTER JOIN (False)

        Returns:
            Self for chaining
        """
        for attr in attrs:
            if inner:
                self._stmt = self._stmt.join(attr)
            else:
                self._stmt = self._stmt.outerjoin(attr)
        return self

    def eager_load(self, *paths: InstrumentedAttribute) -> QueryBuilder[T]:
        """Add eager loading for relationships.

        Args:
            *paths: Relationship paths to eager load

        Returns:
            Self for chaining
        """

        for path in paths:
            parts = str(path).split(".")
            if len(parts) == 1:
                self._eager_load_paths.append((path,))
            else:
                self._eager_load_paths.append(path)
        return self

    def order_by(self, *clauses: InstrumentedAttribute | str) -> QueryBuilder[T]:
        """Add ordering to the query.

        Args:
            *clauses: Ordering clauses

        Returns:
            Self for chaining
        """
        self._stmt = self._stmt.order_by(*clauses)
        return self

    def limit(self, limit: int) -> QueryBuilder[T]:
        """Add a limit clause.

        Args:
            limit: Maximum number of results

        Returns:
            Self for chaining
        """
        self._stmt = self._stmt.limit(limit)
        return self

    def offset(self, offset: int) -> QueryBuilder[T]:
        """Add an offset clause.

        Args:
            offset: Number of results to skip

        Returns:
            Self for chaining
        """
        self._stmt = self._stmt.offset(offset)
        return self

    def _apply_filters(self) -> None:
        """Apply accumulated filter conditions."""
        if self._filter_conditions:
            self._stmt = self._stmt.where(*self._filter_conditions)

    def _apply_eager_loads(self) -> None:
        """Apply accumulated eager loading options."""
        if not self._eager_load_paths:
            return

        from sqlalchemy.orm import joinedload

        for path in self._eager_load_paths:
            if len(path) == 1:
                self._stmt = self._stmt.options(joinedload(path[0]))
            else:
                # Build nested eager load
                option = joinedload(path[0])
                for attr in path[1:]:
                    option = option.joinedload(attr)
                self._stmt = self._stmt.options(option)

    def first(self) -> T | None:
        """Execute query and return the first result.

        Returns:
            The first result or None
        """
        self._apply_filters()
        self._apply_eager_loads()
        return self._session.scalar(self._stmt)

    def all(self) -> list[T]:
        """Execute query and return all results.

        Returns:
            List of results
        """
        self._apply_filters()
        self._apply_eager_loads()
        return list(self._session.scalars(self._stmt).all())

    def count(self) -> int:
        """Execute query and return count.

        Returns:
            Number of results
        """
        self._apply_filters()
        return self._session.scalar(select(func.count()).select_from(self._stmt))


class UnitOfWork(ABC):
    """Unit of Work pattern for managing transactions.

    Provides a way to group repository operations into atomic transactions.
    Services can request needed repositories and commit/rollback as a unit.
    """

    @abstractmethod
    def commit(self) -> None:
        """Commit all pending changes."""

    @abstractmethod
    def rollback(self) -> None:
        """Rollback all pending changes."""

    @abstractmethod
    def flush(self) -> None:
        """Flush pending changes without committing."""


class SQLAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy-based Unit of Work implementation."""

    def __init__(self, session: Session) -> None:
        """Initialize the Unit of Work.

        Args:
            session: SQLAlchemy ORM session
        """
        self._session = session

    def commit(self) -> None:
        """Commit all pending changes."""
        self._session.commit()

    def rollback(self) -> None:
        """Rollback all pending changes."""
        self._session.rollback()

    def flush(self) -> None:
        """Flush pending changes without committing."""
        self._session.flush()

    @property
    def session(self) -> Session:
        """Get the underlying SQLAlchemy session.

        Returns:
            The database session
        """
        return self._session

    @contextmanager
    def transaction(self) -> Iterable[None]:
        """Context manager for a transaction.

        Yields:
            None

        Example:
            with uow.transaction():
                # perform operations
                uow.commit()
        """
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise


def with_repository(
    repo_method: Callable[..., T],
) -> Callable[..., T]:
    """Decorator to ensure repository operations run within a session.

    Args:
        repo_method: A repository method to wrap

    Returns:
        The wrapped method

    This decorator can be used on service layer methods to ensure
    they have proper database session handling.
    """

    def wrapper(self, *args: Any, **kwargs: Any) -> T:
        # The service layer should manage sessions via dependency injection
        # This decorator is a placeholder for future session management logic
        return repo_method(self, *args, **kwargs)

    return wrapper
