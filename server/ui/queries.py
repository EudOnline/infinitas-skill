"""Service layer for UI-related database queries.

This module provides a clean separation between the UI layer and database access,
following the principle that UI code should not directly access the database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.models import (
    AccessGrant,
    AuditEvent,
    Credential,
    Job,
    Release,
    ReviewCase,
    Skill,
    SkillVersion,
)
from server.modules.audit.read_model import activity_query

# ── Skill/Release lookup services ───────────────────────────────────────────


def get_skill_or_404(db: Session, skill_id: int) -> Skill:
    """Get a skill by ID or raise 404.

    Args:
        db: Database session
        skill_id: Skill ID

    Returns:
        Skill object

    Raises:
        HTTPException: If skill not found
    """
    from fastapi import HTTPException

    skill = db.get(Skill, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return skill


def get_release_bundle_or_404(db: Session, release_id: int) -> tuple[Release, SkillVersion, Skill]:
    """Get a release with its version and skill.

    Args:
        db: Database session
        release_id: Release ID

    Returns:
        Tuple of (release, version, skill)

    Raises:
        HTTPException: If release, version, or skill not found
    """
    from fastapi import HTTPException

    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="release not found")
    version = db.get(SkillVersion, release.skill_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="skill version not found")
    skill = db.get(Skill, version.skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return release, version, skill


def get_skill_name(db: Session, skill_id: int) -> str | None:
    """Get a skill's display name by ID.

    Args:
        db: Database session
        skill_id: Skill ID

    Returns:
        Display name or None if not found
    """
    skill = db.get(Skill, int(skill_id))
    return skill.display_name if skill else None


def get_release_label(db: Session, release_id: int) -> str | None:
    """Get a release label by ID.

    Args:
        db: Database session
        release_id: Release ID

    Returns:
        Release label or None if not found
    """
    try:
        release = db.get(Release, int(release_id))
    except (TypeError, ValueError):
        return str(release_id)
    if release is None:
        return str(release_id)
    return f"release-{release.id}"


# ── Activity/Stats services ─────────────────────────────────────────────────────


def get_audit_events(db: Session, *, limit: int = 100) -> list[AuditEvent]:
    """Get recent audit events.

    Args:
        db: Database session
        limit: Maximum number of events to return

    Returns:
        List of audit events
    """
    capped_limit = max(1, min(int(limit or 100), 500))
    return list(db.scalars(activity_query().limit(capped_limit)).all())


# ── Dashboard stats services ───────────────────────────────────────────────────


class DashboardCounts:
    """Dashboard count statistics."""

    total_objects: int
    total_releases: int
    total_share_links: int
    total_access: int
    pending_reviews: int
    queued_jobs: int
    running_jobs: int

    def __init__(
        self,
        total_objects: int,
        total_releases: int,
        total_share_links: int,
        total_access: int,
        pending_reviews: int,
        queued_jobs: int,
        running_jobs: int,
    ):
        self.total_objects = total_objects
        self.total_releases = total_releases
        self.total_share_links = total_share_links
        self.total_access = total_access
        self.pending_reviews = pending_reviews
        self.queued_jobs = queued_jobs
        self.running_jobs = running_jobs


def get_dashboard_counts(db: Session) -> DashboardCounts:
    """Get count statistics for the dashboard.

    Args:
        db: Database session

    Returns:
        DashboardCounts object with all statistics
    """
    total_objects = int(db.scalar(select(func.count()).select_from(Skill)) or 0)
    total_releases = int(db.scalar(select(func.count()).select_from(Release)) or 0)
    total_share_links = int(
        db.scalar(
            select(func.count()).select_from(AccessGrant).where(AccessGrant.grant_type == "link")
        )
        or 0
    )
    total_access = int(
        db.scalar(
            select(func.count()).select_from(Credential).where(Credential.type == "grant_token")
        )
        or 0
    )
    pending_reviews = int(
        db.scalar(select(func.count()).select_from(ReviewCase).where(ReviewCase.state == "open"))
        or 0
    )
    queued_jobs = int(
        db.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) or 0
    )
    running_jobs = int(
        db.scalar(select(func.count()).select_from(Job).where(Job.status == "running")) or 0
    )

    return DashboardCounts(
        total_objects=total_objects,
        total_releases=total_releases,
        total_share_links=total_share_links,
        total_access=total_access,
        pending_reviews=pending_reviews,
        queued_jobs=queued_jobs,
        running_jobs=running_jobs,
    )


class UserStats:
    """User-specific statistics."""

    active_tokens: int
    accessible_skills: int
    new_activity: int

    def __init__(self, active_tokens: int, accessible_skills: int, new_activity: int):
        self.active_tokens = active_tokens
        self.accessible_skills = accessible_skills
        self.new_activity = new_activity


def get_user_stats(db: Session, *, days: int = 7) -> UserStats:
    """Get user-specific statistics.

    Args:
        db: Database session
        days: Number of days to look back for activity

    Returns:
        UserStats object with user statistics
    """
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=days)

    active_tokens = int(
        db.scalar(
            select(func.count())
            .select_from(Credential)
            .where(
                Credential.revoked_at.is_(None),
                (Credential.expires_at.is_(None)) | (Credential.expires_at > now),
            )
        )
        or 0
    )
    accessible_skills = int(db.scalar(select(func.count()).select_from(Skill)) or 0)
    new_activity = int(
        db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.occurred_at >= week_ago)
        )
        or 0
    )

    return UserStats(
        active_tokens=active_tokens,
        accessible_skills=accessible_skills,
        new_activity=new_activity,
    )


__all__ = [
    "get_skill_or_404",
    "get_release_bundle_or_404",
    "get_skill_name",
    "get_release_label",
    "get_audit_events",
    "DashboardCounts",
    "get_dashboard_counts",
    "UserStats",
    "get_user_stats",
]
