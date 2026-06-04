"""SkillVersion repository for authoring data access.

This repository handles all SkillVersion-related database operations,
isolating the service layer from SQLAlchemy ORM details.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.modules.authoring.models import SkillVersion
from server.repository.base import SQLAlchemyRepository


class VersionRepository(SQLAlchemyRepository[SkillVersion, int]):
    """Repository for SkillVersion entity operations."""

    def _get_model_type(self) -> type[SkillVersion]:
        """Get the SkillVersion model type."""
        return SkillVersion

    def find_by_skill_and_version(
        self, skill_id: int, version: str
    ) -> SkillVersion | None:
        """Find a version by skill ID and version string.

        Args:
            skill_id: The skill ID
            version: The version string

        Returns:
            The version if found, None otherwise
        """
        return self._session.scalar(
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
            .where(SkillVersion.version == version)
        )

    def find_by_skill_and_version_or_404(
        self, skill_id: int, version: str
    ) -> SkillVersion:
        """Find a version by skill ID and version string or raise NotFoundError.

        Args:
            skill_id: The skill ID
            version: The version string

        Returns:
            The version

        Raises:
            NotFoundError: If the version doesn't exist
        """
        version_obj = self.find_by_skill_and_version(skill_id, version)
        if version_obj is None:
            from server.exceptions import NotFoundError

            raise NotFoundError(f"Version '{version}' not found for skill {skill_id}")
        return version_obj

    def list_by_skill(
        self, skill_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[SkillVersion]:
        """List versions for a skill, most recent first.

        Args:
            skill_id: The skill ID
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of versions
        """
        stmt = (
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
            .order_by(SkillVersion.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def count_by_skill(self, skill_id: int) -> int:
        """Count versions for a skill.

        Args:
            skill_id: The skill ID

        Returns:
            Number of versions
        """
        return self._session.scalar(
            select(func.count())
            .select_from(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
        )

    def get_latest(self, skill_id: int) -> SkillVersion | None:
        """Get the latest version for a skill.

        Args:
            skill_id: The skill ID

        Returns:
            The latest version, or None if no versions exist
        """
        return self._session.scalar(
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
            .order_by(SkillVersion.created_at.desc())
            .limit(1)
        )

    def with_skill(self, version_id: int) -> SkillVersion | None:
        """Get a version (skill relationship is not defined in model).

        Args:
            version_id: The version ID

        Returns:
            The version, or None
        """
        return self.get(version_id)

    def with_skill_or_404(self, version_id: int) -> SkillVersion:
        """Get a version or raise NotFoundError.

        Args:
            version_id: The version ID

        Returns:
            The version

        Raises:
            NotFoundError: If the version doesn't exist
        """
        version_obj = self.get(version_id)
        if version_obj is None:
            from server.exceptions import NotFoundError

            raise NotFoundError(f"Version {version_id} not found")
        return version_obj

    def create(
        self,
        *,
        skill_id: int,
        version: str,
        content_digest: str,
        metadata_digest: str = "",
        sealed_manifest: dict[str, Any] | None = None,
        draft_id: int | None = None,
        created_by: int | None = None,
    ) -> SkillVersion:
        """Create a new version.

        Args:
            skill_id: The skill ID
            version: The version string
            content_digest: Content digest hash
            metadata_digest: Metadata digest hash
            sealed_manifest: Optional sealed manifest dictionary
            draft_id: Optional draft ID this version was created from
            created_by: Optional user/principal ID who created this version

        Returns:
            The created version
        """
        import json

        version_obj = SkillVersion(
            skill_id=skill_id,
            version=version,
            content_digest=content_digest,
            metadata_digest=metadata_digest,
            sealed_manifest_json=json.dumps(sealed_manifest or {}),
            created_from_draft_id=draft_id,
            created_by_principal_id=created_by,
        )
        self._session.add(version_obj)
        self._session.flush()
        return version_obj

    def update_digests(
        self,
        version_id: int,
        *,
        content_digest: str,
        metadata_digest: str,
    ) -> SkillVersion:
        """Update a version's digests.

        Args:
            version_id: The version ID
            content_digest: New content digest
            metadata_digest: New metadata digest

        Returns:
            The updated version
        """
        version_obj = self.get_or_404(version_id)
        version_obj.content_digest = content_digest
        version_obj.metadata_digest = metadata_digest
        self._session.add(version_obj)
        return version_obj

    def update_manifest(
        self, version_id: int, manifest: dict[str, Any]
    ) -> SkillVersion:
        """Update a version's sealed manifest.

        Args:
            version_id: The version ID
            manifest: New sealed manifest dictionary

        Returns:
            The updated version
        """
        import json

        version_obj = self.get_or_404(version_id)
        version_obj.sealed_manifest_json = json.dumps(manifest)
        self._session.add(version_obj)
        return version_obj

    def get_content_digest(self, version_id: int) -> str:
        """Get a version's content digest.

        Args:
            version_id: The version ID

        Returns:
            The version content digest

        Raises:
            NotFoundError: If the version doesn't exist
        """
        version_obj = self.get_or_404(version_id)
        return version_obj.content_digest

    def get_manifest(self, version_id: int) -> dict[str, Any]:
        """Get a version's sealed manifest.

        Args:
            version_id: The version ID

        Returns:
            The version sealed manifest

        Raises:
            NotFoundError: If the version doesn't exist
        """
        import json

        version_obj = self.get_or_404(version_id)
        if version_obj.sealed_manifest_json:
            return json.loads(version_obj.sealed_manifest_json)
        return {}

    def version_exists(self, skill_id: int, version: str) -> bool:
        """Check if a version string already exists for a skill.

        Args:
            skill_id: The skill ID
            version: The version string

        Returns:
            True if the version exists, False otherwise
        """
        return self._session.scalar(
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
            .where(SkillVersion.version == version)
        ) is not None

    def list_recent(
        self,
        *,
        skill_ids: list[int] | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[SkillVersion]:
        """List recent versions across skills.

        Args:
            skill_ids: Optional list of skill IDs to filter by
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of versions
        """
        stmt = select(SkillVersion)

        if skill_ids:
            stmt = stmt.where(SkillVersion.skill_id.in_(skill_ids))

        stmt = stmt.order_by(SkillVersion.created_at.desc()).offset(skip).limit(limit)
        return list(self._session.scalars(stmt).all())
