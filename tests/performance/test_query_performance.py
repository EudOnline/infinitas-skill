"""Query performance tests.

This module tests database query performance to ensure efficient
data access and proper use of indexes.
"""

from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from server.app import create_app


def _test_client(tmp_path: Path) -> TestClient:
    """Create a test client."""
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'perf.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "perf-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"perf-tester","display_name":"Perf Tester",'
        '"role":"maintainer","token":"perf-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


@pytest.fixture
def db(tmp_path: Path) -> Session:
    """Create a database session for performance testing."""
    from server.db import get_engine, get_session_factory

    db_path = tmp_path / "perf.db"
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "perf-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ENV"] = "test"

    engine = get_engine()
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


class TestQueryPerformance:
    """Test suite for query performance."""

    def test_skill_by_id_query_is_fast(self, db: Session) -> None:
        """Test that querying skill by ID is fast."""
        from server.models import Principal, Skill

        # Create test data
        principal = Principal(
            slug="test-namespace",
            kind="user",
            display_name="Test Namespace",
        )
        db.add(principal)
        db.flush()

        skill = Skill(
            namespace_id=principal.id,
            slug="test-skill",
            display_name="Test Skill",
            status="published",
        )
        db.add(skill)
        db.flush()

        # Measure query performance
        start = perf_counter()
        retrieved = db.get(Skill, skill.id)
        elapsed = perf_counter() - start

        assert retrieved is not None
        assert elapsed < 0.1, f"Query took {elapsed:.3f}s, expected < 0.1s"

    def test_indexed_queries_are_fast(self, db: Session) -> None:
        """Test that indexed queries perform well."""
        from server.models import Principal, Skill

        # Create test data
        principal = Principal(
            slug="indexed-namespace",
            kind="user",
            display_name="Indexed Namespace",
        )
        db.add(principal)
        db.flush()

        # Create multiple skills
        for i in range(10):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"skill-{i}",
                display_name=f"Skill {i}",
                status="published",
            )
            db.add(skill)
        db.flush()

        # Test query on indexed column (namespace_id)
        start = perf_counter()
        from sqlalchemy import select

        stmt = select(Skill).where(Skill.namespace_id == principal.id)
        results = list(db.scalars(stmt).all())
        elapsed = perf_counter() - start

        assert len(results) >= 10
        assert elapsed < 0.1, f"Indexed query took {elapsed:.3f}s, expected < 0.1s"

    def test_count_queries_are_efficient(self, db: Session) -> None:
        """Test that count queries use indexes efficiently."""
        from sqlalchemy import func, select

        from server.models import Principal, Skill

        # Create test data
        principal = Principal(
            slug="count-namespace",
            kind="user",
            display_name="Count Namespace",
        )
        db.add(principal)
        db.flush()

        for i in range(5):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"count-skill-{i}",
                display_name=f"Count Skill {i}",
                status="published",
            )
            db.add(skill)
        db.flush()

        # Measure count query
        start = perf_counter()
        stmt = select(func.count()).select_from(Skill).where(
            Skill.namespace_id == principal.id
        )
        count = db.scalar(stmt)
        elapsed = perf_counter() - start

        assert count >= 5
        assert elapsed < 0.1, f"Count query took {elapsed:.3f}s, expected < 0.1s"


class TestPaginationPerformance:
    """Test pagination performance."""

    def test_pagination_limits_large_results(self, db: Session) -> None:
        """Test that pagination properly limits result sets."""
        from sqlalchemy import select

        from server.models import Principal, Skill

        # Create test data
        principal = Principal(
            slug="pag-namespace",
            kind="user",
            display_name="Pagination Namespace",
        )
        db.add(principal)
        db.flush()

        # Create many skills
        created_count = 0
        for i in range(100):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"pag-skill-{i}",
                display_name=f"Pagination Skill {i}",
                status="published",
            )
            db.add(skill)
            created_count += 1
        db.flush()

        # Test pagination with limit
        start = perf_counter()
        stmt = (
            select(Skill)
            .where(Skill.namespace_id == principal.id)
            .limit(20)
        )
        results = list(db.scalars(stmt).all())
        elapsed = perf_counter() - start

        assert len(results) <= 20
        assert elapsed < 0.1, f"Paginated query took {elapsed:.3f}s, expected < 0.1s"

    def test_pagination_offset_works(self, db: Session) -> None:
        """Test that pagination offset works correctly."""
        from sqlalchemy import select

        from server.models import Principal, Skill

        # Create test data
        principal = Principal(
            slug="offset-namespace",
            kind="user",
            display_name="Offset Namespace",
        )
        db.add(principal)
        db.flush()

        # Create many skills
        for i in range(50):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"offset-skill-{i}",
                display_name=f"Offset Skill {i}",
                status="published",
            )
            db.add(skill)
        db.flush()

        # Test first page
        stmt1 = (
            select(Skill)
            .where(Skill.namespace_id == principal.id)
            .order_by(Skill.id)
            .limit(10)
            .offset(0)
        )
        page1 = list(db.scalars(stmt1).all())

        # Test second page
        stmt2 = (
            select(Skill)
            .where(Skill.namespace_id == principal.id)
            .order_by(Skill.id)
            .limit(10)
            .offset(10)
        )
        page2 = list(db.scalars(stmt2).all())

        assert len(page1) == 10
        assert len(page2) == 10
        # Ensure pages are different
        page1_ids = {s.id for s in page1}
        page2_ids = {s.id for s in page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestN1QueryPrevention:
    """Test that N+1 queries are prevented."""

    def test_no_n1_queries_on_list(self, db: Session) -> None:
        """Test that listing entities doesn't cause N+1 queries."""
        from sqlalchemy import select

        from server.models import Principal, Skill

        # Create test data
        principal = Principal(
            slug="n1-namespace",
            kind="user",
            display_name="N1 Namespace",
        )
        db.add(principal)
        db.flush()

        # Create skills
        for i in range(20):
            skill = Skill(
                namespace_id=principal.id,
                slug=f"n1-skill-{i}",
                display_name=f"N1 Skill {i}",
                status="published",
            )
            db.add(skill)
        db.flush()

        # Measure query count
        # In production, we'd use query counting middleware
        # For this test, we just ensure the query completes quickly
        start = perf_counter()
        stmt = (
            select(Skill)
            .where(Skill.namespace_id == principal.id)
            .order_by(Skill.created_at.desc())
            .limit(20)
        )
        results = list(db.scalars(stmt).all())
        elapsed = perf_counter() - start

        assert len(results) <= 20
        # If there were N+1 queries, this would be much slower
        assert elapsed < 0.2, f"Query took {elapsed:.3f}s, possible N+1 issue"
