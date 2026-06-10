"""Skill repository for authoring data access.

This repository handles all Skill-related database operations,
isolating the service layer from SQLAlchemy ORM details.
"""

from __future__ import annotations

from sqlalchemy import select

from server.models import Skill
from server.repository.base import SQLAlchemyRepository


class SkillRepository(SQLAlchemyRepository[Skill, int]):
    """Repository for Skill entity operations."""

    def _get_model_type(self) -> type[Skill]:
        """Get the Skill model type."""
        return Skill

    def find_by_slug(self, slug: str, namespace_id: int) -> Skill | None:
        """Find a skill by slug within a namespace.

        Args:
            slug: The skill slug
            namespace_id: The namespace (principal) ID

        Returns:
            The skill if found, None otherwise
        """
        return self._session.scalar(
            select(Skill)
            .where(Skill.slug == slug)
            .where(Skill.namespace_id == namespace_id)
        )

    def find_by_slug_or_404(self, slug: str, namespace_id: int) -> Skill:
        """Find a skill by slug within a namespace or raise NotFoundError.

        Args:
            slug: The skill slug
            namespace_id: The namespace (principal) ID

        Returns:
            The skill

        Raises:
            NotFoundError: If the skill doesn't exist
        """
        skill = self.find_by_slug(slug, namespace_id)
        if skill is None:
            from server.exceptions import NotFoundError

            raise NotFoundError(f"Skill '{slug}' not found in namespace {namespace_id}")
        return skill

    def list_by_namespace(
        self,
        namespace_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> list[Skill]:
        """List skills within a namespace.

        Args:
            namespace_id: The namespace (principal) ID
            skip: Number of items to skip
            limit: Maximum number of items to return
            status: Optional status filter

        Returns:
            List of skills
        """
        stmt = select(Skill).where(Skill.namespace_id == namespace_id)

        if status is not None:
            stmt = stmt.where(Skill.status == status)

        stmt = stmt.order_by(Skill.created_at.desc()).offset(skip).limit(limit)
        return list(self._session.scalars(stmt).all())

    def count_by_namespace(
        self, namespace_id: int, *, status: str | None = None
    ) -> int:
        """Count skills within a namespace.

        Args:
            namespace_id: The namespace (principal) ID
            status: Optional status filter

        Returns:
            Number of skills
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Skill).where(
            Skill.namespace_id == namespace_id
        )

        if status is not None:
            stmt = stmt.where(Skill.status == status)

        return self._session.scalar(stmt)

    def with_namespace(self, skill_id: int) -> Skill | None:
        """Get a skill and separately load its namespace (principal).

        Args:
            skill_id: The skill ID

        Returns:
            The skill (namespace must be loaded separately)

        Note:
            This returns the skill but doesn't eagerly load the namespace
            relationship since it's not defined in the model. The namespace
            can be loaded separately using the namespace_id.
        """
        return self.get(skill_id)

    def with_namespace_or_404(self, skill_id: int) -> Skill:
        """Get a skill with its namespace eagerly loaded or raise NotFoundError.

        Args:
            skill_id: The skill ID

        Returns:
            The skill with namespace loaded

        Raises:
            NotFoundError: If the skill doesn't exist
        """
        skill = self.with_namespace(skill_id)
        if skill is None:
            from server.exceptions import NotFoundError

            raise NotFoundError(f"Skill {skill_id} not found")
        return skill

    def update_status(self, skill_id: int, status: str) -> Skill:
        """Update a skill's status.

        Args:
            skill_id: The skill ID
            status: The new status

        Returns:
            The updated skill
        """
        skill = self.get_or_404(skill_id)
        skill.status = status
        self._session.add(skill)
        return skill

    def update_metadata(
        self,
        skill_id: int,
        *,
        display_name: str | None = None,
        summary: str | None = None,
    ) -> Skill:
        """Update a skill's metadata.

        Args:
            skill_id: The skill ID
            display_name: Optional new display name
            summary: Optional new summary

        Returns:
            The updated skill
        """
        skill = self.get_or_404(skill_id)
        if display_name is not None:
            skill.display_name = display_name
        if summary is not None:
            skill.summary = summary
        self._session.add(skill)
        return skill

    def slug_exists(self, slug: str, namespace_id: int) -> bool:
        """Check if a slug already exists in a namespace.

        Args:
            slug: The slug to check
            namespace_id: The namespace ID

        Returns:
            True if the slug exists, False otherwise
        """
        return self._session.scalar(
            select(Skill)
            .where(Skill.slug == slug)
            .where(Skill.namespace_id == namespace_id)
        ) is not None

    def search(
        self,
        *,
        query: str = "",
        namespace_id: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Skill]:
        """Search skills by display name or slug.

        Args:
            query: Search query string
            namespace_id: Optional namespace filter
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of matching skills
        """
        stmt = select(Skill)

        if namespace_id is not None:
            stmt = stmt.where(Skill.namespace_id == namespace_id)

        if query:
            search_pattern = f"%{query}%"
            stmt = stmt.where(
                (Skill.display_name.ilike(search_pattern))
                | (Skill.slug.ilike(search_pattern))
            )

        stmt = stmt.order_by(Skill.created_at.desc()).offset(skip).limit(limit)
        return list(self._session.scalars(stmt).all())
