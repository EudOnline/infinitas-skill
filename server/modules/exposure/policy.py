from __future__ import annotations

from typing import Any


def build_exposure_policy() -> dict[str, dict[str, Any]]:
    return {
        "private": {
            "allowed_requested_review_modes": ["none"],
            "effective_requested_review_mode": "none",
            "effective_review_requirement": "none",
        },
        "authenticated": {
            "allowed_requested_review_modes": ["none"],
            "effective_requested_review_mode": "none",
            "effective_review_requirement": "none",
        },
        "grant": {
            "allowed_requested_review_modes": ["none", "advisory", "blocking"],
            "effective_requested_review_mode": None,
            "effective_review_requirement": None,
        },
        "public": {
            "allowed_requested_review_modes": ["blocking"],
            "effective_requested_review_mode": "blocking",
            "effective_review_requirement": "blocking",
        },
    }


def derive_exposure_action_state(
    *,
    exposure: object,
    review_case_state: str,
) -> dict[str, object]:
    state = str(getattr(exposure, "state", "") or "").strip().lower()
    review_requirement = str(getattr(exposure, "review_requirement", "") or "").strip().lower()
    can_patch = state not in {"revoked", "rejected"}
    can_revoke = state in {"pending_policy", "review_open", "active"}
    if state in {"active", "revoked", "rejected"}:
        return {
            "can_activate": False,
            "can_revoke": can_revoke,
            "can_patch": can_patch,
            "activation_block_reason": "",
        }
    if review_requirement == "blocking":
        if review_case_state == "approved":
            return {
                "can_activate": True,
                "can_revoke": can_revoke,
                "can_patch": can_patch,
                "activation_block_reason": "",
            }
        block_reason = {
            "open": "blocking_review_open",
            "rejected": "blocking_review_rejected",
        }.get(review_case_state, "blocking_review_unapproved")
        return {
            "can_activate": False,
            "can_revoke": can_revoke,
            "can_patch": can_patch,
            "activation_block_reason": block_reason,
        }
    return {
        "can_activate": state in {"pending_policy", "review_open"},
        "can_revoke": can_revoke,
        "can_patch": can_patch,
        "activation_block_reason": "",
    }
