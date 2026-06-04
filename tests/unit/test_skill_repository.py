"""Tests for SkillRepository.

This module tests the repository pattern implementation for Skill entities.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from server.models import Principal, Skill
from server.modules.authoring.repositories import SkillRepository


@pytest.fixture
def skill_repo(db: Session) -> SkillRepository:
    """Create a SkillRepository instance."""
    return SkillRepository(db)


@pytest.fixture
def test_principal(db: Session) -> Principal:
    """Create a test principal (namespace)."""
    principal = Principal(
        slug="test-namespace",
        kind="user",
        display_name="Test Namespace",
    )
    db.add(principal)
    db.flush()
    return principal


@pytest.fixture
def test_skill(db: Session, test_principal: Principal) -> Skill:
    """Create a test skill."""
    skill = Skill(
        namespace_id=test_principal.id,
        slug="test-skill",
        display_name="Test Skill",
        summary="A test skill",
        status="draft",
    )
    db.add(skill)
    db.flush()
    return skill


class TestSkillRepository:
    """Test suite for SkillRepository."""

    def test_create_skill(
        self, skill_repo: SkillRepository, test_principal: Principal
    ) -> None:
        """Test creating a new skill."""
        skill = Skill(
            namespace_id=test_principal.id,
            slug="new-skill",
            display_name="New Skill",
            summary="A new skill",
            status="draft",
        )
        skill_repo.add(skill)
        skill_repo.flush()

        retrieved = skill_repo.get(skill.id)
        assert retrieved is not None
        assert retrieved.slug == "new-skill"
        assert retrieved.display_name == "New Skill"

    def test_get_skill_by_id(self, skill_repo: SkillRepository, test_skill: Skill) -> None:
        """Test getting a skill by ID."""
        retrieved = skill_repo.get(test_skill.id)
        assert retrieved is not None
        assert retrieved.id == test_skill.id
        assert retrieved.slug == test_skill.slug

    def test_get_nonexistent_skill(self, skill_repo: SkillRepository) -> None:
        """Test getting a nonexistent skill returns None."""
        retrieved = skill_repo.get(99999)
        assert retrieved is None

    def test_get_or_404_existing(self, skill_repo: SkillRepository, test_skill: Skill) -> None:
        """Test get_or_404 with existing skill."""
        retrieved = skill_repo.get_or_404(test_skill.id)
        assert retrieved.id == test_skill.id

    def test_get_or_404_nonexistent(self, skill_repo: SkillRepository) -> None:
        """Test get_or_404 with nonexistent skill raises NotFoundError."""
        from server.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            skill_repo.get_or_404(99999)

    def test_find_by_slug(
        self, skill_repo: SkillRepository, test_skill: Skill, test_principal: Principal
    ) -> None:
        """Test finding a skill by slug and namespace."""
        retrieved = skill_repo.find_by_slug("test-skill", test_principal.id)
        assert retrieved is not None
        assert retrieved.id == test_skill.id

    def test_find_by_slug_not_found(
        self, skill_repo: SkillRepository, test_principal: Principal
    ) -> None:
        """Test finding a nonexistent slug returns None."""
        retrieved = skill_repo.find_by_slug("nonexistent", test_principal.id)
        assert retrieved is None

    def test_slug_exists(self, skill_repo: SkillRepository, test_skill: Skill) -> None:
        """Test checking if a slug exists."""
        assert skill_repo.slug_exists("test-skill", test_skill.namespace_id) is True
        assert skill_repo.slug_exists("nonexistent", test_skill.namespace_id) is False

    def test_list_by_namespace(
        self, skill_repo: SkillRepository, test_principal: Principal, db: Session
    ) -> None:
        """Test listing skills by namespace."""
        # Create multiple skills
        for i in range(3):
            skill = Skill(
                namespace_id=test_principal.id,
                slug=f"skill-{i}",
                display_name=f"Skill {i}",
                status="draft",
            )
            db.add(skill)
        db.flush()

        skills = skill_repo.list_by_namespace(test_principal.id)
        assert len(skills) >= 3

    def test_list_by_namespace_with_filters(
        self, skill_repo: SkillRepository, test_principal: Principal, db: Session
    ) -> None:
        """Test listing skills with status filter."""
        # Create skills with different statuses
        draft_skill = Skill(
            namespace_id=test_principal.id,
            slug="draft-skill",
            display_name="Draft Skill",
            status="draft",
        )
        published_skill = Skill(
            namespace_id=test_principal.id,
            slug="published-skill",
            display_name="Published Skill",
            status="published",
        )
        db.add(draft_skill)
        db.add(published_skill)
        db.flush()

        draft_skills = skill_repo.list_by_namespace(
            test_principal.id, status="draft"
        )
        published_skills = skill_repo.list_by_namespace(
            test_principal.id, status="published"
        )

        assert any(s.slug == "draft-skill" for s in draft_skills)
        assert any(s.slug == "published-skill" for s in published_skills)

    def test_count_by_namespace(
        self, skill_repo: SkillRepository, test_principal: Principal, db: Session
    ) -> None:
        """Test counting skills by namespace."""
        initial_count = skill_repo.count_by_namespace(test_principal.id)

        # Add some skills
        for i in range(3):
            skill = Skill(
                namespace_id=test_principal.id,
                slug=f"count-skill-{i}",
                display_name=f"Count Skill {i}",
                status="draft",
            )
            db.add(skill)
        db.flush()

        new_count = skill_repo.count_by_namespace(test_principal.id)
        assert new_count == initial_count + 3

    def test_update_status(self, skill_repo: SkillRepository, test_skill: Skill) -> None:
        """Test updating skill status."""
        updated = skill_repo.update_status(test_skill.id, "published")
        assert updated.status == "published"

    def test_update_metadata(self, skill_repo: SkillRepository, test_skill: Skill) -> None:
        """Test updating skill metadata."""
        updated = skill_repo.update_metadata(
            test_skill.id,
            display_name="Updated Name",
            summary="Updated summary",
        )
        assert updated.display_name == "Updated Name"
        assert updated.summary == "Updated summary"

    def test_with_namespace(
        self, skill_repo: SkillRepository, test_skill: Skill
    ) -> None:
        """Test getting skill (namespace loaded separately)."""
        skill = skill_repo.with_namespace(test_skill.id)
        assert skill is not None
        assert skill.id == test_skill.id
        assert skill.namespace_id == test_skill.namespace_id

    def test_search(self, skill_repo: SkillRepository, test_principal: Principal, db: Session) -> None:
        """Test searching skills by query."""
        # Create searchable skills
        skill1 = Skill(
            namespace_id=test_principal.id,
            slug="python-helper",
            display_name="Python Helper",
            status="published",
        )
        skill2 = Skill(
            namespace_id=test_principal.id,
            slug="javascript-tool",
            display_name="JavaScript Tool",
            status="published",
        )
        db.add(skill1)
        db.add(skill2)
        db.flush()

        results = skill_repo.search(query="python")
        assert len(results) > 0
        assert any("python" in s.slug.lower() or "python" in s.display_name.lower() for s in results)

    def test_delete_skill(self, skill_repo: SkillRepository, db: Session) -> None:
        """Test deleting a skill."""
        skill = Skill(
            namespace_id=1,
            slug="delete-me",
            display_name="Delete Me",
            status="draft",
        )
        db.add(skill)
        db.flush()

        skill_id = skill.id
        skill_repo.delete(skill)
        db.flush()

        assert skill_repo.get(skill_id) is None
