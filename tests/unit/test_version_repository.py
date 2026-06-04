"""Tests for VersionRepository.

This module tests the repository pattern implementation for SkillVersion entities.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from server.models import Principal, Skill
from server.modules.authoring.models import SkillVersion
from server.modules.authoring.repositories import SkillRepository, VersionRepository


@pytest.fixture
def version_repo(db: Session) -> VersionRepository:
    """Create a VersionRepository instance."""
    return VersionRepository(db)


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
        status="published",
    )
    db.add(skill)
    db.flush()
    return skill, principal


@pytest.fixture
def test_version(db: Session, version_repo: VersionRepository, test_skill: tuple[Skill, Principal]) -> SkillVersion:
    """Create a test version."""
    skill, _ = test_skill
    version = version_repo.create(
        skill_id=skill.id,
        version="1.0.0",
        content_digest="sha256:abc123",
        metadata_digest="sha256:def456",
        sealed_manifest={"key": "value"},
        created_by=1,
    )
    return version


class TestVersionRepository:
    """Test suite for VersionRepository."""

    def test_create_version(self, version_repo: VersionRepository, test_skill: tuple[Skill, Principal]) -> None:
        """Test creating a new version."""
        skill, _ = test_skill
        version = version_repo.create(
            skill_id=skill.id,
            version="1.0.0",
            content_digest="sha256:newcontent",
            metadata_digest="sha256:newmetadata",
            sealed_manifest={"version": "1.0.0"},
        )

        assert version.id is not None
        assert version.skill_id == skill.id
        assert version.version == "1.0.0"

    def test_get_version_by_id(self, version_repo: VersionRepository, test_version: SkillVersion) -> None:
        """Test getting a version by ID."""
        retrieved = version_repo.get(test_version.id)
        assert retrieved is not None
        assert retrieved.id == test_version.id

    def test_find_by_skill_and_version(
        self, version_repo: VersionRepository, test_skill: tuple[Skill, Principal], test_version: SkillVersion
    ) -> None:
        """Test finding a version by skill ID and version string."""
        skill, _ = test_skill
        retrieved = version_repo.find_by_skill_and_version(skill.id, "1.0.0")
        assert retrieved is not None
        assert retrieved.id == test_version.id

    def test_find_nonexistent_version(self, version_repo: VersionRepository) -> None:
        """Test finding a nonexistent version returns None."""
        retrieved = version_repo.find_by_skill_and_version(99999, "1.0.0")
        assert retrieved is None

    def test_version_exists(self, version_repo: VersionRepository, test_skill: tuple[Skill, Principal], test_version: SkillVersion) -> None:
        """Test checking if a version exists."""
        skill, _ = test_skill
        assert version_repo.version_exists(skill.id, "1.0.0") is True
        assert version_repo.version_exists(skill.id, "2.0.0") is False

    def test_list_by_skill(
        self, version_repo: VersionRepository, test_skill: tuple[Skill, Principal], db: Session
    ) -> None:
        """Test listing versions by skill."""
        skill, _ = test_skill

        # Create multiple versions
        for i in range(3):
            version_repo.create(
                skill_id=skill.id,
                version=f"0.{i}.0",
                content_digest=f"sha256:content{i}",
                metadata_digest=f"sha256:metadata{i}",
                created_by=1,
            )
        db.flush()

        versions = version_repo.list_by_skill(skill.id)
        assert len(versions) >= 3

    def test_count_by_skill(self, version_repo: VersionRepository, test_skill: tuple[Skill, Principal]) -> None:
        """Test counting versions by skill."""
        skill, _ = test_skill

        # Create some versions
        for i in range(2):
            version_repo.create(
                skill_id=skill.id,
                version=f"1.{i}.0",
                content_digest=f"sha256:count{i}",
                metadata_digest=f"sha256:meta{i}",
                created_by=1,
            )

        count = version_repo.count_by_skill(skill.id)
        assert count >= 2

    def test_get_latest(self, version_repo: VersionRepository, test_skill: tuple[Skill, Principal]) -> None:
        """Test getting the latest version for a skill."""
        skill, _ = test_skill

        # Create multiple versions
        version_repo.create(
            skill_id=skill.id,
            version="0.1.0",
            content_digest="sha256:old",
            metadata_digest="sha256:oldmeta",
            created_by=1,
        )
        version_repo.create(
            skill_id=skill.id,
            version="1.0.0",
            content_digest="sha256:new",
            metadata_digest="sha256:newmeta",
            created_by=1,
        )

        latest = version_repo.get_latest(skill.id)
        assert latest is not None
        assert latest.version == "1.0.0"

    def test_with_skill(self, version_repo: VersionRepository, test_version: SkillVersion) -> None:
        """Test getting version."""
        version = version_repo.with_skill(test_version.id)
        assert version is not None
        assert version.id == test_version.id

    def test_update_digests(self, version_repo: VersionRepository, test_version: SkillVersion) -> None:
        """Test updating version digests."""
        updated = version_repo.update_digests(
            test_version.id,
            content_digest="sha256:updated",
            metadata_digest="sha256:updatedmeta",
        )
        assert updated.content_digest == "sha256:updated"
        assert updated.metadata_digest == "sha256:updatedmeta"

    def test_update_manifest(self, version_repo: VersionRepository, test_version: SkillVersion) -> None:
        """Test updating version manifest."""
        new_manifest = {"version": "2.0.0", "author": "test"}
        version_repo.update_manifest(test_version.id, new_manifest)

        manifest = version_repo.get_manifest(test_version.id)
        assert manifest["version"] == "2.0.0"

    def test_get_content_digest(self, version_repo: VersionRepository, test_version: SkillVersion) -> None:
        """Test getting version content digest."""
        digest = version_repo.get_content_digest(test_version.id)
        assert digest == "sha256:abc123"

    def test_get_manifest(self, version_repo: VersionRepository, test_version: SkillVersion) -> None:
        """Test getting version manifest."""
        manifest = version_repo.get_manifest(test_version.id)
        assert manifest["key"] == "value"

    def test_list_recent(self, version_repo: VersionRepository, test_skill: tuple[Skill, Principal], db: Session) -> None:
        """Test listing recent versions across skills."""
        skill, _ = test_skill

        # Create versions
        for i in range(3):
            version_repo.create(
                skill_id=skill.id,
                version=f"2.{i}.0",
                content_digest=f"sha256:recent{i}",
                metadata_digest=f"sha256:recentmeta{i}",
                created_by=1,
            )
        db.flush()

        recent = version_repo.list_recent(skill_ids=[skill.id], limit=5)
        assert len(recent) >= 3
