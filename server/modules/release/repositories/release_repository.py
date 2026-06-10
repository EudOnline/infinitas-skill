"""Release repository for release data access.

This repository handles all Release-related database operations,
isolating the service layer from SQLAlchemy ORM details.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from server.modules.release.models import Release
from server.repository.base import SQLAlchemyRepository


class ReleaseRepository(SQLAlchemyRepository[Release, int]):
    """Repository for Release entity operations."""

    def _get_model_type(self) -> type[Release]:
        """Get the Release model type."""
        return Release

    def find_by_skill_and_version(
        self, skill_id: int, version: str
    ) -> Release | None:
        """Find a release by skill ID and version string.

        This requires joining with SkillVersion to match the version string.

        Args:
            skill_id: The skill ID
            version: The version string

        Returns:
            The release if found, None otherwise
        """
        from server.modules.authoring.models import SkillVersion

        return self._session.scalar(
            select(Release)
            .join(SkillVersion, Release.skill_version_id == SkillVersion.id)
            .where(Release.skill_id == skill_id)
            .where(SkillVersion.version == version)
        )

    def find_by_skill_and_version_or_404(
        self, skill_id: int, version: str
    ) -> Release:
        """Find a release by skill ID and version string or raise NotFoundError.

        Args:
            skill_id: The skill ID
            version: The version string

        Returns:
            The release

        Raises:
            NotFoundError: If the release doesn't exist
        """
        release = self.find_by_skill_and_version(skill_id, version)
        if release is None:
            from server.exceptions import NotFoundError

            raise NotFoundError(f"Release for version '{version}' not found for skill {skill_id}")
        return release

    def list_by_skill(
        self, skill_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[Release]:
        """List releases for a skill.

        Args:
            skill_id: The skill ID
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of releases
        """
        stmt = (
            select(Release)
            .where(Release.skill_id == skill_id)
            .order_by(Release.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def count_by_skill(self, skill_id: int) -> int:
        """Count releases for a skill.

        Args:
            skill_id: The skill ID

        Returns:
            Number of releases
        """
        return self._session.scalar(
            select(func.count())
            .select_from(Release)
            .where(Release.skill_id == skill_id)
        )

    def with_skill(self, release_id: int) -> Release | None:
        """Get a release (skill relationship is not defined in model).

        Args:
            release_id: The release ID

        Returns:
            The release, or None
        """
        return self.get(release_id)

    def with_skill_or_404(self, release_id: int) -> Release:
        """Get a release or raise NotFoundError.

        Args:
            release_id: The release ID

        Returns:
            The release

        Raises:
            NotFoundError: If the release doesn't exist
        """
        release = self.get(release_id)
        if release is None:
            from server.exceptions import NotFoundError

            raise NotFoundError(f"Release {release_id} not found")
        return release

    def with_version(self, release_id: int) -> Release | None:
        """Get a release (version relationship is not defined in model).

        Args:
            release_id: The release ID

        Returns:
            The release, or None
        """
        return self.get(release_id)

    def with_full_details(self, release_id: int) -> Release | None:
        """Get a release (relationships not defined in model).

        Args:
            release_id: The release ID

        Returns:
            The release, or None
        """
        return self.get(release_id)

    def with_full_details_or_404(self, release_id: int) -> Release:
        """Get a release or raise NotFoundError.

        Args:
            release_id: The release ID

        Returns:
            The release

        Raises:
            NotFoundError: If the release doesn't exist
        """
        release = self.get(release_id)
        if release is None:
            from server.exceptions import NotFoundError

            raise NotFoundError(f"Release {release_id} not found")
        return release

    def create(
        self,
        *,
        skill_id: int,
        skill_version_id: int,
        state: str = "preparing",
        format_version: str = "1",
        created_by: int | None = None,
    ) -> Release:
        """Create a new release.

        Args:
            skill_id: The skill ID
            skill_version_id: The skill version ID
            state: The initial state (default: preparing)
            format_version: The format version (default: 1)
            created_by: Optional user/principal ID who created this release

        Returns:
            The created release
        """
        release = Release(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            state=state,
            format_version=format_version,
            created_by_principal_id=created_by,
        )
        self._session.add(release)
        self._session.flush()
        return release

    def update_state(self, release_id: int, state: str) -> Release:
        """Update a release's state.

        Args:
            release_id: The release ID
            state: The new state

        Returns:
            The updated release
        """
        release = self.get_or_404(release_id)
        release.state = state
        self._session.add(release)
        return release

    def update_platform_compatibility(
        self, release_id: int, compatibility: dict[str, Any]
    ) -> Release:
        """Update a release's platform compatibility.

        Args:
            release_id: The release ID
            compatibility: New platform compatibility dictionary

        Returns:
            The updated release
        """
        import json

        release = self.get_or_404(release_id)
        release.platform_compatibility_json = json.dumps(compatibility)
        self._session.add(release)
        return release

    def get_platform_compatibility(self, release_id: int) -> dict[str, Any]:
        """Get a release's platform compatibility.

        Args:
            release_id: The release ID

        Returns:
            The release platform compatibility

        Raises:
            NotFoundError: If the release doesn't exist
        """
        import json

        release = self.get_or_404(release_id)
        if release.platform_compatibility_json:
            return json.loads(release.platform_compatibility_json)
        return {}

    def find_by_state(self, state: str, *, skip: int = 0, limit: int = 50) -> list[Release]:
        """Find releases by state.

        Args:
            state: The state to filter by
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of releases in the given state
        """
        stmt = (
            select(Release)
            .where(Release.state == state)
            .order_by(Release.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def count_by_state(self, state: str) -> int:
        """Count releases by state.

        Args:
            state: The state to count

        Returns:
            Number of releases in the given state
        """
        return self._session.scalar(
            select(func.count())
            .select_from(Release)
            .where(Release.state == state)
        )

    def list_pending_materialization(
        self, *, skip: int = 0, limit: int = 50
    ) -> list[Release]:
        """List releases pending materialization.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of releases that need materialization
        """
        return self.find_by_state("preparing", skip=skip, limit=limit)

    def find_existing(
        self, skill_id: int, skill_version_id: int
    ) -> Release | None:
        """Find an existing release for a skill and version.

        Used to check if a release already exists before creating one.

        Args:
            skill_id: The skill ID
            skill_version_id: The skill version ID

        Returns:
            The release if found, None otherwise
        """
        return self._session.scalar(
            select(Release)
            .where(Release.skill_id == skill_id)
            .where(Release.skill_version_id == skill_version_id)
        )

    def find_existing_or_create(
        self, skill_id: int, skill_version_id: int
    ) -> tuple[Release, bool]:
        """Find an existing release or create a new one.

        Args:
            skill_id: The skill ID
            skill_version_id: The skill version ID

        Returns:
            Tuple of (release, created) where created is True if a new release was created
        """
        existing = self.find_existing(skill_id, skill_version_id)
        if existing:
            return existing, False
        return (
            self.create(
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                state="preparing",
            ),
            True,
        )
