"""Skill management service.

Handles skill CRUD operations and access control.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from server.modules.authoring.models import Skill
from server.modules.authoring.repository import (
    create_skill,
    get_skill,
    get_skill_by_namespace_and_slug,
)
from server.modules.authoring.schemas import SkillCreateRequest
from server.modules.authoring.services.base import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from server.modules.memory.service import record_lifecycle_memory_event_best_effort

# ── Skill CRUD ───────────────────────────────────────────────────────────────


def get_skill_or_404(db: Session, skill_id: int) -> Skill:
    """Get a skill by ID or raise 404.

    Args:
        db: Database session
        skill_id: Skill ID

    Returns:
        Skill object

    Raises:
        NotFoundError: If skill not found
    """
    skill = get_skill(db, skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    return skill


def create_new_skill(
    db: Session,
    *,
    namespace_id: int,
    actor_principal_id: int,
    payload: SkillCreateRequest,
) -> Skill:
    """Create a new skill.

    Args:
        db: Database session
        namespace_id: Namespace (principal) ID
        actor_principal_id: Principal creating the skill
        payload: Skill creation request

    Returns:
        Created Skill object

    Raises:
        ConflictError: If skill slug already exists
        ForbiddenError: If user lacks access to namespace
    """
    existing = get_skill_by_namespace_and_slug(
        db,
        namespace_id=namespace_id,
        slug=payload.slug,
    )
    if existing is not None:
        raise ConflictError("skill slug already exists in namespace")

    assert_namespace_access(
        db,
        namespace_id=namespace_id,
        principal_id=actor_principal_id,
        is_maintainer=False,
    )

    skill = create_skill(
        db,
        namespace_id=namespace_id,
        slug=payload.slug,
        display_name=payload.display_name,
        summary=payload.summary,
        created_by_principal_id=actor_principal_id,
    )
    db.commit()
    db.refresh(skill)

    record_lifecycle_memory_event_best_effort(
        db,
        lifecycle_event="task.authoring.create_skill",
        aggregate_type="skill",
        aggregate_id=str(skill.id),
        actor_ref=f"principal:{actor_principal_id}",
        payload={
            "skill_id": str(skill.id),
            "skill_slug": skill.slug,
            "display_name": skill.display_name,
        },
    )

    return skill


# ── Access Control ─────────────────────────────────────────────────────────


def _check_team_access(db: Session, namespace_id: int, principal_id: int) -> bool:
    """Check if principal has team access to namespace.

    Args:
        db: Database session
        namespace_id: Namespace ID
        principal_id: Principal ID

    Returns:
        True if principal has team access
    """
    from server.modules.access.service import (
        get_team_for_namespace,
        is_principal_team_member,
    )

    team = get_team_for_namespace(db, namespace_id=namespace_id)
    if team is None:
        return False
    return is_principal_team_member(db, team_id=team.id, principal_id=principal_id)


def assert_namespace_access(
    db: Session,
    *,
    namespace_id: int,
    principal_id: int,
    is_maintainer: bool = False,
) -> None:
    """Assert that principal has access to namespace.

    Args:
        db: Database session
        namespace_id: Namespace ID
        principal_id: Principal ID
        is_maintainer: Whether the actor is a maintainer

    Raises:
        ForbiddenError: If principal lacks access
    """
    if is_maintainer:
        return

    from server.modules.access.service import get_principal

    principal = get_principal(db, principal_id)
    if principal is None:
        raise ForbiddenError("principal not found")

    if principal.id == namespace_id:
        return

    if _check_team_access(db, namespace_id=namespace_id, principal_id=principal_id):
        return

    raise ForbiddenError("principal does not have access to namespace")


def assert_namespace_owner(
    db: Session,
    *,
    skill: Skill,
    principal_id: int,
    is_maintainer: bool = False,
) -> None:
    """Assert that principal owns the skill's namespace.

    Args:
        db: Database session
        skill: Skill object
        principal_id: Principal ID
        is_maintainer: Whether the actor is a maintainer

    Raises:
        ForbiddenError: If principal is not the namespace owner
    """
    if is_maintainer:
        return

    from server.modules.access.service import get_principal

    principal = get_principal(db, principal_id)
    if principal is None:
        raise ForbiddenError("principal not found")

    if principal.id == skill.namespace_id:
        return

    if _check_team_access(db, namespace_id=skill.namespace_id, principal_id=principal_id):
        return

    raise ForbiddenError("principal does not own the skill's namespace")


__all__ = [
    "get_skill_or_404",
    "create_new_skill",
    "assert_namespace_access",
    "assert_namespace_owner",
    "_check_team_access",
]
