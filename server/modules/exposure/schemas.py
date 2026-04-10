from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from server.modules.exposure.models import Exposure


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _load_policy_snapshot(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


class ExposureCreateRequest(BaseModel):
    audience_type: str
    listing_mode: Literal["listed", "direct_only"] = "listed"
    install_mode: Literal["enabled", "disabled"] = "enabled"
    requested_review_mode: str = "none"


class ExposurePatchRequest(BaseModel):
    listing_mode: Literal["listed", "direct_only"] | None = None
    install_mode: Literal["enabled", "disabled"] | None = None
    requested_review_mode: str | None = None


class ExposureView(BaseModel):
    id: int
    release_id: int
    audience_type: str
    listing_mode: str
    install_mode: str
    review_requirement: str
    requested_review_mode: str
    state: str
    requested_by_principal_id: int | None = None
    policy_snapshot: dict
    activated_at: str | None = None
    ended_at: str | None = None

    @classmethod
    def from_model(cls, exposure: Exposure) -> "ExposureView":
        snapshot = _load_policy_snapshot(exposure.policy_snapshot_json)
        return cls(
            id=exposure.id,
            release_id=exposure.release_id,
            audience_type=exposure.audience_type,
            listing_mode=exposure.listing_mode,
            install_mode=exposure.install_mode,
            review_requirement=exposure.review_requirement,
            requested_review_mode=str(snapshot.get("requested_review_mode") or "none"),
            state=exposure.state,
            requested_by_principal_id=exposure.requested_by_principal_id,
            policy_snapshot=snapshot,
            activated_at=_iso(exposure.activated_at),
            ended_at=_iso(exposure.ended_at),
        )
