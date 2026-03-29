from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from server.models import AccessCredential, AccessGrant, Namespace, Release, Skill, SkillVersion, User


def find_user_by_token(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    return db.query(User).filter(User.token == token).one_or_none()


def find_access_credential_by_token(token: str | None, db: Session) -> AccessCredential | None:
    if not token:
        return None
    return (
        db.query(AccessCredential)
        .options(
            joinedload(AccessCredential.grant)
            .joinedload(AccessGrant.release)
            .joinedload(Release.skill_version)
            .joinedload(SkillVersion.skill)
            .joinedload(Skill.namespace)
        )
        .filter(AccessCredential.token == token, AccessCredential.revoked_at.is_(None))
        .one_or_none()
    )
