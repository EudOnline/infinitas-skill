"""Pagination tests.

This module tests pagination behavior to ensure proper limits,
offsets, and performance characteristics.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from server.db import get_engine, get_session_factory


@pytest.fixture
def db(tmp_path: Path) -> Session:
    """Create a database session for pagination testing."""
    db_path = tmp_path / "pagination.db"
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "pag-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ENV"] = "test"

    get_engine()
    session_factory = get_session_factory()

    # Run migrations
    from alembic.config import Config

    from alembic import command

    ROOT = Path(__file__).resolve().parents[2]
    alembic_dir = ROOT / "alembic"
    if alembic_dir.exists():
        alembic_cfg = Config(str(ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        command.upgrade(alembic_cfg, "head")

    session = session_factory()
    yield session

    session.close()


class TestPaginationBasics:
    """Test basic pagination functionality."""

    def test_empty_result_set_with_pagination(self, db: Session) -> None:
        """Test pagination with empty result set."""
        from sqlalchemy import select

        from server.modules.authoring.models import Skill
        from server.modules.identity.models import Principal

        principal = Principal(
            slug="empty-pagination",
            kind="user",
            display_name="Empty Pagination",
        )
        db.add(principal)
        db.flush()

        # Query with pagination on empty set
        stmt = select(Skill).where(Skill.namespace_id == principal.id).limit(10).offset(0)
        results = list(db.scalars(stmt).all())

        assert len(results) == 0

    def test_pagination_respects_limit(self, db: Session) -> None:
        """Test that pagination respects the limit parameter."""
        from sqlalchemy import select

        from server.modules.authoring.models import Skill
        from server.modules.identity.models import Principal

        principal = Principal(
            slug="limit-pagination",
            kind="user",
            display_name="Limit Pagination",
        )
        db.add(principal)
        db.flush()

        # Create 25 skills
        for i in range(25):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"limit-skill-{i}",
                display_name=f"Limit Skill {i}",
                status="published",
            )
            db.add(skill)
        db.flush()

        # Test with limit 10
        stmt = select(Skill).where(Skill.namespace_id == principal.id).limit(10)
        results = list(db.scalars(stmt).all())

        assert len(results) == 10

    def test_pagination_respects_offset(self, db: Session) -> None:
        """Test that pagination respects the offset parameter."""
        from sqlalchemy import select

        from server.modules.authoring.models import Skill
        from server.modules.identity.models import Principal

        principal = Principal(
            slug="offset-pagination",
            kind="user",
            display_name="Offset Pagination",
        )
        db.add(principal)
        db.flush()

        # Create 20 skills
        for i in range(20):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"offset-skill-{i}",
                display_name=f"Offset Skill {i}",
                status="published",
            )
            db.add(skill)
        db.flush()

        # First page
        stmt1 = (
            select(Skill)
            .where(Skill.namespace_id == principal.id)
            .order_by(Skill.id)
            .limit(5)
            .offset(0)
        )
        page1 = list(db.scalars(stmt1).all())

        # Second page
        stmt2 = (
            select(Skill)
            .where(Skill.namespace_id == principal.id)
            .order_by(Skill.id)
            .limit(5)
            .offset(5)
        )
        page2 = list(db.scalars(stmt2).all())

        assert len(page1) == 5
        assert len(page2) == 5

        # Verify pages don't overlap
        page1_ids = {s.id for s in page1}
        page2_ids = {s.id for s in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_pagination_beyond_data_returns_empty(self, db: Session) -> None:
        """Test that pagination beyond available data returns empty set."""
        from sqlalchemy import select

        from server.modules.authoring.models import Skill
        from server.modules.identity.models import Principal

        principal = Principal(
            slug="beyond-pagination",
            kind="user",
            display_name="Beyond Pagination",
        )
        db.add(principal)
        db.flush()

        # Create only 5 skills
        for i in range(5):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"beyond-skill-{i}",
                display_name=f"Beyond Skill {i}",
                status="published",
            )
            db.add(skill)
        db.flush()

        # Request page beyond available data
        stmt = select(Skill).where(Skill.namespace_id == principal.id).limit(10).offset(100)
        results = list(db.scalars(stmt).all())

        assert len(results) == 0


class TestPaginationParameters:
    """Test pagination parameter validation."""

    def test_default_limit_is_reasonable(self, db: Session) -> None:
        """Test that default pagination limit is reasonable."""
        from server.pagination import PaginationParams

        # Default limit should be set
        params = PaginationParams()
        assert params.limit > 0
        assert params.limit <= 100

    def test_max_limit_is_enforced(self, db: Session) -> None:
        """Test that maximum pagination limit is enforced."""
        import inspect

        from annotated_types import Le

        from server.pagination import query_pagination_params

        limit_query = inspect.signature(query_pagination_params).parameters["limit"].default
        max_limits = [
            constraint.le for constraint in limit_query.metadata if isinstance(constraint, Le)
        ]

        assert max_limits == [100]

    def test_skip_parameter_works(self, db: Session) -> None:
        """Test that skip parameter works correctly."""
        from server.pagination import PaginationParams

        params = PaginationParams(skip=50, limit=10)
        assert params.skip == 50
        assert params.limit == 10


class TestPaginationPerformance:
    """Test pagination performance characteristics."""

    def test_large_offset_performance(self, db: Session) -> None:
        """Test that large offsets don't cause performance issues."""
        from time import perf_counter

        from sqlalchemy import select

        from server.modules.authoring.models import Skill
        from server.modules.identity.models import Principal

        principal = Principal(
            slug="large-offset",
            kind="user",
            display_name="Large Offset",
        )
        db.add(principal)
        db.flush()

        # Create 100 skills
        for i in range(100):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"large-offset-skill-{i}",
                display_name=f"Large Offset Skill {i}",
                status="published",
            )
            db.add(skill)
        db.flush()

        # Query with large offset
        start = perf_counter()
        stmt = select(Skill).where(Skill.namespace_id == principal.id).limit(10).offset(90)
        results = list(db.scalars(stmt).all())
        elapsed = perf_counter() - start

        assert len(results) <= 10
        # Large offsets should still be reasonably fast
        assert elapsed < 0.2, f"Large offset query took {elapsed:.3f}s"

    def test_count_query_is_fast(self, db: Session) -> None:
        """Test that count queries for pagination are fast."""
        from time import perf_counter

        from sqlalchemy import func, select

        from server.modules.authoring.models import Skill
        from server.modules.identity.models import Principal

        principal = Principal(
            slug="count-query",
            kind="user",
            display_name="Count Query",
        )
        db.add(principal)
        db.flush()

        # Create 50 skills
        for i in range(50):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"count-skill-{i}",
                display_name=f"Count Skill {i}",
                status="published",
            )
            db.add(skill)
        db.flush()

        # Count query
        start = perf_counter()
        stmt = select(func.count()).select_from(Skill).where(Skill.namespace_id == principal.id)
        count = db.scalar(stmt)
        elapsed = perf_counter() - start

        assert count >= 50
        assert elapsed < 0.1, f"Count query took {elapsed:.3f}s"
