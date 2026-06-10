"""SkillDraft repository for authoring data access.

This repository handles all SkillDraft-related database operations,
isolating the service layer from SQLAlchemy ORM details.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from server.modules.authoring.models import SkillDraft
from server.repository.base import SQLAlchemyRepository


class DraftRepository(SQLAlchemyRepository[SkillDraft, int]):
    """Repository for SkillDraft entity operations."""

    def _get_model_type(self) -> type[SkillDraft]:
        """Get the SkillDraft model type."""
        return SkillDraft

    def find_by_skill(self, skill_id: int) -> SkillDraft | None:
        """Find the current draft for a skill.

        Args:
            skill_id: The skill ID

        Returns:
            The draft if found, None otherwise
        """
        return self._session.scalar(
            select(SkillDraft)
            .where(SkillDraft.skill_id == skill_id)
            .order_by(SkillDraft.id.desc())
        )

    def find_by_skill_or_404(self, skill_id: int) -> SkillDraft:
        """Find the current draft for a skill or raise NotFoundError.

        Args:
            skill_id: The skill ID

        Returns:
            The draft

        Raises:
            NotFoundError: If no draft exists
        """
        draft = self.find_by_skill(skill_id)
        if draft is None:
            from server.exceptions import NotFoundError

            raise NotFoundError(f"No draft found for skill {skill_id}")
        return draft

    def list_by_skill(self, skill_id: int, *, limit: int = 10) -> list[SkillDraft]:
        """List all drafts for a skill, most recent first.

        Args:
            skill_id: The skill ID
            limit: Maximum number of drafts to return

        Returns:
            List of drafts
        """
        stmt = (
            select(SkillDraft)
            .where(SkillDraft.skill_id == skill_id)
            .order_by(SkillDraft.updated_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def count_by_skill(self, skill_id: int) -> int:
        """Count drafts for a skill.

        Args:
            skill_id: The skill ID

        Returns:
            Number of drafts
        """
        return self._session.scalar(
            select(func.count())
            .select_from(SkillDraft)
            .where(SkillDraft.skill_id == skill_id)
        )

    def with_skill(self, draft_id: int) -> SkillDraft | None:
        """Get a draft (skill relationship is not defined in model).

        Args:
            draft_id: The draft ID

        Returns:
            The draft, or None
        """
        return self.get(draft_id)

    def with_skill_or_404(self, draft_id: int) -> SkillDraft:
        """Get a draft or raise NotFoundError.

        Args:
            draft_id: The draft ID

        Returns:
            The draft

        Raises:
            NotFoundError: If the draft doesn't exist
        """
        draft = self.get(draft_id)
        if draft is None:
            from server.exceptions import NotFoundError

            raise NotFoundError(f"Draft {draft_id} not found")
        return draft

    def create(
        self,
        *,
        skill_id: int,
        content_ref: str = "",
        content_mode: str = "external_ref",
        state: str = "open",
        base_version_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        updated_by: int | None = None,
    ) -> SkillDraft:
        """Create a new draft.

        Args:
            skill_id: The skill ID
            content_ref: Draft content reference (URL, path, etc.)
            content_mode: Content storage mode
            state: Draft state
            base_version_id: Optional base version ID
            metadata: Optional metadata dictionary
            updated_by: Optional user/principal ID who updated this draft

        Returns:
            The created draft
        """
        import json

        draft = SkillDraft(
            skill_id=skill_id,
            content_ref=content_ref,
            content_mode=content_mode,
            state=state,
            base_version_id=base_version_id,
            metadata_json=json.dumps(metadata or {}),
            updated_by_principal_id=updated_by,
        )
        self._session.add(draft)
        self._session.flush()
        return draft

    def update_content_ref(
        self,
        draft_id: int,
        *,
        content_ref: str,
    ) -> SkillDraft:
        """Update a draft's content reference.

        Args:
            draft_id: The draft ID
            content_ref: New content reference

        Returns:
            The updated draft
        """
        draft = self.get_or_404(draft_id)
        draft.content_ref = content_ref
        self._session.add(draft)
        return draft

    def update_metadata(
        self, draft_id: int, metadata: dict[str, Any]
    ) -> SkillDraft:
        """Update a draft's metadata.

        Args:
            draft_id: The draft ID
            metadata: New metadata dictionary

        Returns:
            The updated draft
        """
        import json

        draft = self.get_or_404(draft_id)
        draft.metadata_json = json.dumps(metadata)
        self._session.add(draft)
        return draft

    def get_content_ref(self, draft_id: int) -> str:
        """Get a draft's content reference.

        Args:
            draft_id: The draft ID

        Returns:
            The draft content reference

        Raises:
            NotFoundError: If the draft doesn't exist
        """
        draft = self.get_or_404(draft_id)
        return draft.content_ref

    def get_metadata(self, draft_id: int) -> dict[str, Any]:
        """Get a draft's metadata.

        Args:
            draft_id: The draft ID

        Returns:
            The draft metadata

        Raises:
            NotFoundError: If the draft doesn't exist
        """
        import json

        draft = self.get_or_404(draft_id)
        if draft.metadata_json:
            return json.loads(draft.metadata_json)
        return {}

    def delete_by_skill(self, skill_id: int) -> int:
        """Delete all drafts for a skill.

        Args:
            skill_id: The skill ID

        Returns:
            Number of drafts deleted
        """
        drafts = self.list_by_skill(skill_id, limit=1000)
        count = len(drafts)
        for draft in drafts:
            self._session.delete(draft)
        return count

    def update_state(self, draft_id: int, state: str) -> SkillDraft:
        """Update a draft's state.

        Args:
            draft_id: The draft ID
            state: The new state

        Returns:
            The updated draft
        """
        draft = self.get_or_404(draft_id)
        draft.state = state
        self._session.add(draft)
        return draft
