"""Tests for DraftRepository.

This module tests the repository pattern implementation for SkillDraft entities.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from server.models import Principal, Skill
from server.modules.authoring.models import SkillDraft
from server.modules.authoring.repositories import DraftRepository, SkillRepository


@pytest.fixture
def draft_repo(db: Session) -> DraftRepository:
    """Create a DraftRepository instance."""
    return DraftRepository(db)


@pytest.fixture
def skill_repo(db: Session) -> SkillRepository:
    """Create a SkillRepository instance."""
    return SkillRepository(db)


@pytest.fixture
def test_skill(db: Session) -> tuple[Skill, Principal]:
    """Create a test skill and principal."""
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
        summary="A test skill",
        status="draft",
    )
    db.add(skill)
    db.flush()
    return skill, principal


@pytest.fixture
def test_draft(db: Session, draft_repo: DraftRepository, test_skill: tuple[Skill, Principal]) -> SkillDraft:
    """Create a test draft."""
    skill, _ = test_skill
    draft = draft_repo.create(
        skill_id=skill.id,
        content_ref="git+https://example.com/test.git",
        metadata={"version": "1.0.0"},
        updated_by=1,
    )
    return draft


class TestDraftRepository:
    """Test suite for DraftRepository."""

    def test_create_draft(self, draft_repo: DraftRepository, test_skill: tuple[Skill, Principal]) -> None:
        """Test creating a new draft."""
        skill, _ = test_skill
        draft = draft_repo.create(
            skill_id=skill.id,
            content_ref="git+https://example.com/new.git",
            content_mode="external_ref",
            metadata={"key": "value"},
        )

        assert draft.id is not None
        assert draft.skill_id == skill.id
        assert draft.content_ref == "git+https://example.com/new.git"

    def test_get_draft_by_id(self, draft_repo: DraftRepository, test_draft: SkillDraft) -> None:
        """Test getting a draft by ID."""
        retrieved = draft_repo.get(test_draft.id)
        assert retrieved is not None
        assert retrieved.id == test_draft.id

    def test_find_by_skill(self, draft_repo: DraftRepository, test_skill: tuple[Skill, Principal], test_draft: SkillDraft) -> None:
        """Test finding a draft by skill ID."""
        skill, _ = test_skill
        retrieved = draft_repo.find_by_skill(skill.id)
        assert retrieved is not None
        assert retrieved.id == test_draft.id

    def test_find_by_skill_not_found(self, draft_repo: DraftRepository) -> None:
        """Test finding a draft for a skill with no drafts."""
        from server.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            draft_repo.find_by_skill_or_404(99999)

    def test_list_by_skill(self, draft_repo: DraftRepository, test_skill: tuple[Skill, Principal], db: Session) -> None:
        """Test listing drafts by skill."""
        skill, _ = test_skill

        # Create multiple drafts
        for i in range(3):
            draft_repo.create(
                skill_id=skill.id,
                content_ref=f"git+https://example.com/test{i}.git",
                updated_by=1,
            )
        db.flush()

        drafts = draft_repo.list_by_skill(skill.id)
        assert len(drafts) >= 3

    def test_count_by_skill(self, draft_repo: DraftRepository, test_skill: tuple[Skill, Principal]) -> None:
        """Test counting drafts by skill."""
        skill, _ = test_skill

        # Create some drafts
        for i in range(2):
            draft_repo.create(
                skill_id=skill.id,
                content_ref=f"git+https://example.com/count{i}.git",
                updated_by=1,
            )

        count = draft_repo.count_by_skill(skill.id)
        assert count >= 2

    def test_with_skill(self, draft_repo: DraftRepository, test_draft: SkillDraft) -> None:
        """Test getting draft."""
        draft = draft_repo.with_skill(test_draft.id)
        assert draft is not None
        assert draft.id == test_draft.id

    def test_update_content_ref(self, draft_repo: DraftRepository, test_draft: SkillDraft) -> None:
        """Test updating draft content reference."""
        updated = draft_repo.update_content_ref(
            test_draft.id,
            content_ref="git+https://example.com/updated.git",
        )
        assert updated.content_ref == "git+https://example.com/updated.git"

    def test_update_metadata(self, draft_repo: DraftRepository, test_draft: SkillDraft) -> None:
        """Test updating draft metadata."""
        new_metadata = {"version": "2.0.0", "author": "test"}
        updated = draft_repo.update_metadata(test_draft.id, new_metadata)

        metadata = draft_repo.get_metadata(test_draft.id)
        assert metadata["version"] == "2.0.0"
        assert metadata["author"] == "test"

    def test_get_content_ref(self, draft_repo: DraftRepository, test_draft: SkillDraft) -> None:
        """Test getting draft content reference."""
        content_ref = draft_repo.get_content_ref(test_draft.id)
        assert content_ref == "git+https://example.com/test.git"

    def test_get_metadata(self, draft_repo: DraftRepository, test_draft: SkillDraft) -> None:
        """Test getting draft metadata."""
        metadata = draft_repo.get_metadata(test_draft.id)
        assert metadata["version"] == "1.0.0"

    def test_update_state(self, draft_repo: DraftRepository, test_draft: SkillDraft) -> None:
        """Test updating draft state."""
        updated = draft_repo.update_state(test_draft.id, "sealed")
        assert updated.state == "sealed"

    def test_delete_by_skill(self, draft_repo: DraftRepository, test_skill: tuple[Skill, Principal], db: Session) -> None:
        """Test deleting all drafts for a skill."""
        skill, _ = test_skill

        # Create multiple drafts
        for i in range(3):
            draft_repo.create(
                skill_id=skill.id,
                content_ref=f"git+https://example.com/delete{i}.git",
                updated_by=1,
            )
        db.flush()

        count = draft_repo.delete_by_skill(skill.id)
        db.flush()
        assert count >= 3

        # Verify no drafts remain
        assert draft_repo.find_by_skill(skill.id) is None
