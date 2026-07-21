from __future__ import annotations

import secrets
from typing import Any, cast

from sqlalchemy.orm import Session

from server.logging import get_logger
from server.model_base import utcnow
from server.modules.audit.service import append_audit_event
from server.modules.identity.models import User
from server.modules.identity.passwords import hash_password, verify_password
from server.modules.identity.service import (
    ensure_personal_credential_for_user,
    ensure_user_principal,
    get_personal_credential,
    hash_token,
    revoke_principal_credentials,
)
from server.settings import Settings


def _audit_bootstrap_change(
    session: Session,
    *,
    user: User,
    principal_id: int,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    append_audit_event(
        session,
        aggregate_type="user",
        aggregate_id=str(user.id),
        event_type=event_type,
        actor_ref="system:bootstrap",
        owner_principal_id=principal_id,
        payload=payload,
    )


def _disable_removed_users(
    session: Session,
    *,
    existing: dict[str, User],
    configured_names: set[str],
) -> None:
    for username, user in existing.items():
        if username in configured_names:
            continue
        principal = ensure_user_principal(session, user)
        revoked_count = revoke_principal_credentials(session, principal_id=principal.id)
        was_enabled = user.password_hash is not None or revoked_count > 0
        user.password_hash = None
        cast(Any, user).updated_at = utcnow()
        session.add(user)
        if was_enabled:
            _audit_bootstrap_change(
                session,
                user=user,
                principal_id=principal.id,
                event_type="user.disabled",
                payload={"credentials_revoked": revoked_count},
            )


def _apply_bootstrap_password(
    session: Session,
    *,
    user: User,
    principal_id: int,
    password: str,
    log: Any,
) -> None:
    if not password or verify_password(password, user.password_hash):
        return
    try:
        user.password_hash = hash_password(password)
    except ValueError as exc:
        log.warning("bootstrap user %s password skipped: %s", user.username, exc)
        return
    revoked_count = revoke_principal_credentials(
        session,
        principal_id=principal_id,
        credential_types={"session"},
    )
    _audit_bootstrap_change(
        session,
        user=user,
        principal_id=principal_id,
        event_type="user.password.rotated",
        payload={"sessions_revoked": revoked_count},
    )


def seed_bootstrap_users(session: Session, settings: Settings) -> None:
    log = get_logger("server.bootstrap")
    existing = {user.username: user for user in session.query(User).all()}
    configured_names = {item["username"] for item in settings.bootstrap_users}
    _disable_removed_users(session, existing=existing, configured_names=configured_names)
    for item in settings.bootstrap_users:
        user = existing.get(item["username"])
        if user is None:
            user = User(
                username=item["username"],
                display_name=item["display_name"],
                role=item["role"],
            )
            session.add(user)
            session.flush()
            existing[user.username] = user
        if user.display_name != item["display_name"] or user.role != item["role"]:
            user.display_name = item["display_name"]
            user.role = item["role"]
        principal = ensure_user_principal(session, user)
        _apply_bootstrap_password(
            session,
            user=user,
            principal_id=principal.id,
            password=item.get("password", ""),
            log=log,
        )
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
            token_rotated = (
                personal_credential is not None
                and personal_credential.hashed_secret != hash_token(token)
            )
            ensure_personal_credential_for_user(
                session,
                user=user,
                principal=principal,
                raw_token=token,
            )
            if token_rotated:
                _audit_bootstrap_change(
                    session,
                    user=user,
                    principal_id=principal.id,
                    event_type="user.personal_token.rotated",
                    payload={},
                )
        elif settings.environment == "production" and personal_credential is not None:
            cast(Any, personal_credential).revoked_at = utcnow()
            session.add(personal_credential)
            _audit_bootstrap_change(
                session,
                user=user,
                principal_id=principal.id,
                event_type="user.personal_token.revoked",
                payload={},
            )
