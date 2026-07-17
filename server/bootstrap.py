from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from server.logging import get_logger
from server.modules.identity.models import User
from server.modules.identity.passwords import hash_password, verify_password
from server.modules.identity.service import (
    ensure_personal_credential_for_user,
    ensure_user_principal,
    get_personal_credential,
)
from server.settings import Settings


def seed_bootstrap_users(session: Session, settings: Settings) -> None:
    log = get_logger("server.bootstrap")
    existing = {user.username: user for user in session.query(User).all()}
    for item in settings.bootstrap_users:
        user = existing.get(item["username"])
        if user is None:
            user = User(
                username=item["username"],
                display_name=item["display_name"],
                role=item["role"],
            )
            session.add(user)
            existing[user.username] = user
        if user.display_name != item["display_name"] or user.role != item["role"]:
            user.display_name = item["display_name"]
            user.role = item["role"]
        password = item.get("password", "")
        if password and not verify_password(password, user.password_hash):
            try:
                user.password_hash = hash_password(password)
            except ValueError as exc:
                log.warning("bootstrap user %s password skipped: %s", item["username"], exc)
        principal = ensure_user_principal(session, user)
        token = item.get("token")
        personal_credential = get_personal_credential(session, principal_id=principal.id)
        if (
            not token
            and personal_credential is None
            and settings.environment in {"development", "test"}
        ):
            token = f"dev_{secrets.token_urlsafe(24)}"
            log.warning(
                "auto-generated token for bootstrap user %s: %s "
                "(save this token — it will not be shown again)",
                item["username"],
                token,
            )
        if token:
            ensure_personal_credential_for_user(
                session,
                user=user,
                principal=principal,
                raw_token=token,
            )
