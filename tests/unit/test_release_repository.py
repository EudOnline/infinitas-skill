"""Tests for ReleaseRepository.

This module tests the repository pattern implementation for Release entities.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from server.models import Principal, Release, Skill
from server.modules.authoring.models import SkillVersion
from server.modules.authoring.repositories import SkillRepository, VersionRepository
from server.modules.release.repositories import ReleaseRepository


@pytest.fixture
def release_repo(db: Session) -> ReleaseRepository:
    """Create a ReleaseRepository instance."""
    return ReleaseRepository(db)


@pytest.fixture
def skill_repo(db: Session) -> SkillRepository:
    """Create a SkillRepository instance."""
    return SkillRepository(db)


@pytest.fixture
def version_repo(db: Session) -> VersionRepository:
    """Create a VersionRepository instance."""
    return VersionRepository(db)


@pytest.fixture
def test_skill_with_version(db: Session) -> tuple[Skill, SkillVersion, Principal]:
    """Create a test skill, version, and principal."""
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

    version = SkillVersion(
        skill_id=skill.id,
        version="1.0.0",
        content_digest="sha256:abc123",
        metadata_digest="sha256:def456",
        sealed_manifest_json='{"key": "value"}',
    )
    db.add(version)
    db.flush()

    return skill, version, principal


@pytest.fixture
def test_release(db: Session, release_repo: ReleaseRepository, test_skill_with_version: tuple[Skill, SkillVersion, Principal]) -> Release:
    """Create a test release."""
    skill, version, _ = test_skill_with_version
    release = release_repo.create(
        skill_id=skill.id,
        skill_version_id=version.id,
        state="preparing",
    )
    return release


class TestReleaseRepository:
    """Test suite for ReleaseRepository."""

    def test_create_release(self, release_repo: ReleaseRepository, test_skill_with_version: tuple[Skill, SkillVersion, Principal]) -> None:
        """Test creating a new release."""
        skill, version, _ = test_skill_with_version
        release = release_repo.create(
            skill_id=skill.id,
            skill_version_id=version.id,
            state="preparing",
        )

        assert release.id is not None
        assert release.skill_id == skill.id
        assert release.skill_version_id == version.id
        assert release.state == "preparing"

    def test_get_release_by_id(self, release_repo: ReleaseRepository, test_release: Release) -> None:
        """Test getting a release by ID."""
        retrieved = release_repo.get(test_release.id)
        assert retrieved is not None
        assert retrieved.id == test_release.id

    def test_find_by_skill_and_version(
        self, release_repo: ReleaseRepository, test_skill_with_version: tuple[Skill, SkillVersion, Principal], test_release: Release
    ) -> None:
        """Test finding a release by skill ID and version string."""
        skill, version, _ = test_skill_with_version
        retrieved = release_repo.find_by_skill_and_version(skill.id, version.version)
        assert retrieved is not None
        assert retrieved.id == test_release.id

    def test_find_nonexistent_release(self, release_repo: ReleaseRepository) -> None:
        """Test finding a nonexistent release returns None."""
        retrieved = release_repo.find_by_skill_and_version(99999, "1.0.0")
        assert retrieved is None

    def test_find_existing_or_create(
        self, release_repo: ReleaseRepository, test_skill_with_version: tuple[Skill, SkillVersion, Principal]
    ) -> None:
        """Test finding existing release or creating new one."""
        skill, version, _ = test_skill_with_version

        # First call should create
        release1, created1 = release_repo.find_existing_or_create(skill.id, version.id)
        assert created1 is True
        assert release1.id is not None

        # Second call should find existing
        release2, created2 = release_repo.find_existing_or_create(skill.id, version.id)
        assert created2 is False
        assert release2.id == release1.id

    def test_list_by_skill(
        self, release_repo: ReleaseRepository, test_skill_with_version: tuple[Skill, SkillVersion, Principal], db: Session
    ) -> None:
        """Test listing releases by skill."""
        skill, version, _ = test_skill_with_version

        # Create multiple releases with different versions (avoiding 1.0.0 duplicate)
        for i in range(1, 4):
            new_version = SkillVersion(
                skill_id=skill.id,
                version=f"1.{i}.0",
                content_digest=f"sha256:content{i}",
                metadata_digest=f"sha256:metadata{i}",
            )
            db.add(new_version)
            db.flush()

            release_repo.create(
                skill_id=skill.id,
                skill_version_id=new_version.id,
                state="preparing",
            )
        db.flush()

        releases = release_repo.list_by_skill(skill.id)
        assert len(releases) >= 3

    def test_count_by_skill(self, release_repo: ReleaseRepository, test_skill_with_version: tuple[Skill, SkillVersion, Principal], db: Session) -> None:
        """Test counting releases by skill."""
        skill, version, _ = test_skill_with_version

        # Create some releases (avoiding 1.0.0 duplicate)
        for i in range(1, 3):
            new_version = SkillVersion(
                skill_id=skill.id,
                version=f"2.{i}.0",
                content_digest=f"sha256:count{i}",
                metadata_digest=f"sha256:countmeta{i}",
            )
            db.add(new_version)
            db.flush()

            release_repo.create(
                skill_id=skill.id,
                skill_version_id=new_version.id,
                state="preparing",
            )
        db.flush()

        count = release_repo.count_by_skill(skill.id)
        assert count >= 2

    def test_with_skill(self, release_repo: ReleaseRepository, test_release: Release) -> None:
        """Test getting release."""
        release = release_repo.with_skill(test_release.id)
        assert release is not None
        assert release.id == test_release.id

    def test_update_state(self, release_repo: ReleaseRepository, test_release: Release) -> None:
        """Test updating release state."""
        updated = release_repo.update_state(test_release.id, "published")
        assert updated.state == "published"

    def test_update_platform_compatibility(self, release_repo: ReleaseRepository, test_release: Release) -> None:
        """Test updating release platform compatibility."""
        new_compatibility = {"platforms": ["linux", "macos"], "python": ">=3.8"}
        release_repo.update_platform_compatibility(test_release.id, new_compatibility)

        compatibility = release_repo.get_platform_compatibility(test_release.id)
        assert compatibility["platforms"] == ["linux", "macos"]

    def test_get_platform_compatibility(self, release_repo: ReleaseRepository, test_release: Release) -> None:
        """Test getting release platform compatibility."""
        # Set some platform compatibility first
        import json

        test_release.platform_compatibility_json = json.dumps({"key": "value"})
        release_repo._session.add(test_release)
        release_repo._session.flush()

        compatibility = release_repo.get_platform_compatibility(test_release.id)
        assert compatibility["key"] == "value"

    def test_find_by_state(self, release_repo: ReleaseRepository, test_skill_with_version: tuple[Skill, SkillVersion, Principal], db: Session) -> None:
        """Test finding releases by state."""
        skill, version, _ = test_skill_with_version

        # Create releases with different states (using different versions to avoid conflicts)
        version2 = SkillVersion(
            skill_id=skill.id,
            version="2.0.0",
            content_digest="sha256:content2",
            metadata_digest="sha256:metadata2",
        )
        db.add(version2)
        db.flush()

        release_repo.create(
            skill_id=skill.id,
            skill_version_id=version2.id,
            state="published",
        )
        db.flush()

        # Create a preparing release (this is the main release we're testing for)
        release_repo.create(
            skill_id=skill.id,
            skill_version_id=version.id,
            state="preparing",
        )
        db.flush()

        preparing = release_repo.find_by_state("preparing")
        published = release_repo.find_by_state("published")

        assert len(preparing) >= 1
        assert len(published) >= 1

    def test_count_by_state(self, release_repo: ReleaseRepository, test_skill_with_version: tuple[Skill, SkillVersion, Principal], db: Session) -> None:
        """Test counting releases by state."""
        skill, version, _ = test_skill_with_version

        # Create additional releases with different versions to avoid conflicts
        for i in range(1, 3):
            new_version = SkillVersion(
                skill_id=skill.id,
                version=f"3.{i}.0",
                content_digest=f"sha256:state{i}",
                metadata_digest=f"sha256:statemeta{i}",
            )
            db.add(new_version)
            db.flush()

            release_repo.create(
                skill_id=skill.id,
                skill_version_id=new_version.id,
                state="preparing",
            )
        db.flush()

        count = release_repo.count_by_state("preparing")
        assert count >= 2

    def test_list_pending_materialization(self, release_repo: ReleaseRepository, test_skill_with_version: tuple[Skill, SkillVersion, Principal], db: Session) -> None:
        """Test listing releases pending materialization."""
        skill, version, _ = test_skill_with_version

        # Create preparing release
        release_repo.create(
            skill_id=skill.id,
            skill_version_id=version.id,
            state="preparing",
        )
        db.flush()

        pending = release_repo.list_pending_materialization()
        assert len(pending) >= 1
        assert all(r.state == "preparing" for r in pending)
