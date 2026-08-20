from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from server.modules.access.models import AccessGrant
from server.modules.identity.models import Credential, ServicePrincipal
from server.rate_limit import DBRateLimiter

_DAILY_WINDOW_SECONDS = 24 * 60 * 60


class CredentialPolicyError(Exception):
    pass


class CredentialPolicyForbidden(CredentialPolicyError):
    pass


class CredentialPublishQuotaExceeded(CredentialPolicyError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("credential daily publish limit exceeded")
        self.retry_after = retry_after


@dataclass(frozen=True)
class CredentialPolicy:
    readonly: bool
    max_daily_publishes: int | None
    allowed_object_kinds: frozenset[str] | None
    auto_public_publish: bool


def _json_object(raw: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_credential_policy_mapping(db: Session, credential: Credential) -> dict[str, Any]:
    if credential.grant_id is not None:
        grant = db.get(AccessGrant, credential.grant_id)
        if grant is not None:
            return _json_object(grant.constraints_json)
    selector = _json_object(credential.resource_selector_json)
    policy = selector.get("_policy")
    return policy if isinstance(policy, dict) else {}


def resolve_credential_policy(db: Session, credential: Credential) -> CredentialPolicy:
    payload = load_credential_policy_mapping(db, credential)
    max_daily = payload.get("max_daily_publishes")
    if not isinstance(max_daily, int) or isinstance(max_daily, bool):
        max_daily = None

    allowed_raw = payload.get("allowed_object_kinds")
    allowed: frozenset[str] | None = None
    if allowed_raw is not None:
        if not isinstance(allowed_raw, list):
            allowed = frozenset()
        else:
            allowed = frozenset(
                item.strip() for item in allowed_raw if isinstance(item, str) and item.strip()
            )

    return CredentialPolicy(
        readonly=payload.get("readonly") is True,
        max_daily_publishes=max_daily,
        allowed_object_kinds=allowed,
        auto_public_publish=payload.get("auto_public_publish") is True,
    )


def resolve_service_policy(service: ServicePrincipal) -> CredentialPolicy:
    payload = _json_object(service.policy_json)
    max_daily = payload.get("max_daily_publishes")
    if not isinstance(max_daily, int) or isinstance(max_daily, bool):
        max_daily = None
    allowed_raw = payload.get("allowed_object_kinds")
    allowed = None
    if allowed_raw is not None:
        allowed = (
            frozenset(
                item.strip() for item in allowed_raw if isinstance(item, str) and item.strip()
            )
            if isinstance(allowed_raw, list)
            else frozenset()
        )
    return CredentialPolicy(
        readonly=payload.get("readonly") is True,
        max_daily_publishes=max_daily,
        allowed_object_kinds=allowed,
        auto_public_publish=payload.get("auto_public_publish") is True,
    )


def assert_agent_publish_allowed(
    db: Session, *, service: ServicePrincipal, object_kind: str
) -> None:
    policy = resolve_service_policy(service)
    if policy.readonly:
        raise CredentialPolicyForbidden("agent policy is read-only")
    if policy.allowed_object_kinds is not None and object_kind not in policy.allowed_object_kinds:
        raise CredentialPolicyForbidden(f"agent policy does not allow object kind {object_kind!r}")


def consume_publish_quota_for_principal(
    db: Session, *, principal_id: int, service: ServicePrincipal
) -> str:
    policy = resolve_service_policy(service)
    limit = policy.max_daily_publishes
    quota_key = f"agent-publish:{principal_id}"
    if limit is None:
        return quota_key
    if limit <= 0:
        raise CredentialPublishQuotaExceeded(_seconds_until_next_utc_day())
    consumed = DBRateLimiter(db).consume(
        quota_key,
        max_attempts=limit,
        window_seconds=_DAILY_WINDOW_SECONDS,
    )
    if not consumed:
        raise CredentialPublishQuotaExceeded(_seconds_until_next_utc_day())
    return quota_key


def assert_credential_mutation_allowed(
    db: Session,
    *,
    credential: Credential,
    object_kind: str,
) -> None:
    policy = resolve_credential_policy(db, credential)
    if policy.readonly:
        raise CredentialPolicyForbidden("credential is read-only")
    if policy.allowed_object_kinds is not None and object_kind not in policy.allowed_object_kinds:
        raise CredentialPolicyForbidden(
            f"credential policy does not allow object kind {object_kind!r}"
        )


def consume_credential_publish_quota(db: Session, *, credential: Credential) -> None:
    policy = resolve_credential_policy(db, credential)
    limit = policy.max_daily_publishes
    if limit is None:
        return
    if limit <= 0:
        raise CredentialPublishQuotaExceeded(_seconds_until_next_utc_day())
    consumed = DBRateLimiter(db).consume(
        f"credential-publish:{credential.id}",
        max_attempts=limit,
        window_seconds=_DAILY_WINDOW_SECONDS,
    )
    if not consumed:
        raise CredentialPublishQuotaExceeded(_seconds_until_next_utc_day())


def _seconds_until_next_utc_day() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = datetime.fromordinal(now.date().toordinal() + 1).replace(tzinfo=timezone.utc)
    return max(1, int((tomorrow - now).total_seconds()))


__all__ = [
    "CredentialPolicyForbidden",
    "CredentialPublishQuotaExceeded",
    "assert_credential_mutation_allowed",
    "consume_credential_publish_quota",
    "consume_publish_quota_for_principal",
    "assert_agent_publish_allowed",
    "load_credential_policy_mapping",
    "resolve_credential_policy",
    "resolve_service_policy",
]
