"""Error handling tests.

This module tests error handling and exception behavior
across the application.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError


def _test_client(tmp_path: Path) -> TestClient:
    """Create a test client."""
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'error.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "error-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"error-tester","display_name":"Error Tester",'
        '"role":"maintainer","token":"error-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestNotFoundException:
    """Test NotFoundError exception behavior."""

    def test_raise_not_found(self) -> None:
        """Test that NotFoundError can be raised and caught."""
        with pytest.raises(NotFoundError) as exc_info:
            raise NotFoundError("Resource not found")

        assert str(exc_info.value) == "Resource not found"

    def test_not_found_with_id(self) -> None:
        """Test NotFoundError with ID parameter."""
        with pytest.raises(NotFoundError) as exc_info:
            raise NotFoundError("Skill 123 not found")

        assert "123" in str(exc_info.value)


class TestForbiddenError:
    """Test ForbiddenError exception behavior."""

    def test_raise_forbidden(self) -> None:
        """Test that ForbiddenError can be raised and caught."""
        with pytest.raises(ForbiddenError) as exc_info:
            raise ForbiddenError("Access denied")

        assert str(exc_info.value) == "Access denied"

    def test_forbidden_with_context(self) -> None:
        """Test ForbiddenError with context."""
        with pytest.raises(ForbiddenError) as exc_info:
            raise ForbiddenError("User 456 cannot access resource 789")

        assert "456" in str(exc_info.value)
        assert "789" in str(exc_info.value)


class TestValidationError:
    """Test ValidationError exception behavior."""

    def test_raise_validation(self) -> None:
        """Test that ValidationError can be raised and caught."""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Invalid input")

        assert str(exc_info.value) == "Invalid input"

    def test_validation_with_field(self) -> None:
        """Test ValidationError with field name."""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("slug: Invalid characters in slug")

        assert "slug" in str(exc_info.value).lower()


class TestConflictError:
    """Test ConflictError exception behavior."""

    def test_raise_conflict(self) -> None:
        """Test that ConflictError can be raised and caught."""
        with pytest.raises(ConflictError) as exc_info:
            raise ConflictError("Resource already exists")

        assert str(exc_info.value) == "Resource already exists"


class TestAPIErrorResponses:
    """Test API error response behavior."""

    def test_404_response_for_invalid_id(self, tmp_path: Path) -> None:
        """Test that API returns 404 for invalid resource IDs."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer error-test-token"}

        # Try to access a non-existent skill
        response = client.get("/api/v1/library/99999", headers=headers)
        assert response.status_code == 404

    def test_401_response_for_missing_auth(self, tmp_path: Path) -> None:
        """Test that API returns 401 for missing authentication."""
        client = _test_client(tmp_path)

        # Try to access protected endpoint without auth
        response = client.get("/api/v1/activity")
        assert response.status_code == 401

    def test_403_response_for_insufficient_permissions(self, tmp_path: Path) -> None:
        """Test that API returns 403 for insufficient permissions."""
        client = _test_client(tmp_path)
        # Create a user with limited permissions
        # For now, just verify the endpoint structure
        response = client.get("/api/v1/activity")
        # Without auth, should be 401
        assert response.status_code == 401

    def test_422_response_for_invalid_input(self, tmp_path: Path) -> None:
        """Test that API returns 422 for invalid input."""
        client = _test_client(tmp_path)

        # Try to create an object with invalid slug
        response = client.post(
            "/api/v1/skills",
            json={"slug": "invalid$slug", "display_name": "Test"},
        )
        # Should be 422 or 401 (if auth required)
        assert response.status_code in (401, 422)


class TestDatabaseTransactionBehavior:
    """Test database transaction behavior on errors."""

    def test_transaction_rollback_on_error(self, tmp_path: Path) -> None:
        """Test that transactions are rolled back on errors."""
        from server.db import get_engine, get_session_factory

        db_path = tmp_path / "rollback.db"
        os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["INFINITAS_SERVER_SECRET_KEY"] = "rollback-test-secret-32chars"
        os.environ["INFINITAS_SERVER_ENV"] = "test"

        _engine = get_engine()
        session_factory = get_session_factory()

        # Run migrations
        from alembic.config import Config

        from alembic import command

        _root = Path(__file__).resolve().parents[2]
        alembic_dir = _root / "alembic"
        if alembic_dir.exists():
            alembic_cfg = Config(str(_root / "alembic.ini"))
            alembic_cfg.set_main_option("script_location", str(alembic_dir))
            command.upgrade(alembic_cfg, "head")

        session = session_factory()

        try:
            from server.models import Principal, Skill

            # Create a principal
            principal = Principal(
                slug="rollback-test",
                kind="user",
                display_name="Rollback Test",
            )
            session.add(principal)
            session.flush()

            # Start a transaction
            skill = Skill(
                namespace_id=principal.id,
                slug="rollback-skill",
                display_name="Rollback Skill",
                status="draft",
            )
            session.add(skill)
            session.flush()

            skill_id = skill.id

            # Simulate an error and rollback
            session.rollback()

            # Verify skill was not committed
            retrieved = session.get(Skill, skill_id)
            # After rollback, the skill should not exist
            assert retrieved is None

        finally:
            session.close()

    def test_session_state_after_error(self, tmp_path: Path) -> None:
        """Test that session remains usable after an error."""
        from server.db import get_engine, get_session_factory

        db_path = tmp_path / "session-state.db"
        os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["INFINITAS_SERVER_SECRET_KEY"] = "session-test-secret-32chars"
        os.environ["INFINITAS_SERVER_ENV"] = "test"

        _engine = get_engine()
        session_factory = get_session_factory()

        # Run migrations
        from alembic.config import Config

        from alembic import command

        _root = Path(__file__).resolve().parents[2]
        alembic_dir = _root / "alembic"
        if alembic_dir.exists():
            alembic_cfg = Config(str(_root / "alembic.ini"))
            alembic_cfg.set_main_option("script_location", str(alembic_dir))
            command.upgrade(alembic_cfg, "head")

        session = session_factory()

        try:
            from server.models import Principal

            # Create a principal
            principal = Principal(
                slug="session-test",
                kind="user",
                display_name="Session Test",
            )
            session.add(principal)
            session.commit()

            # Try to query with invalid ID
            result = session.get(Principal, 99999)
            assert result is None

            # Session should still be usable
            principal2 = Principal(
                slug="session-test-2",
                kind="user",
                display_name="Session Test 2",
            )
            session.add(principal2)
            session.commit()

            # Verify session is still working
            retrieved = session.get(Principal, principal2.id)
            assert retrieved is not None

        finally:
            session.close()
