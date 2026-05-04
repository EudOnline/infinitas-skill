from __future__ import annotations

from typing import Any

from server.ui.i18n import pick_lang, with_lang


def group_by(items: list[object], key_name: str) -> dict[int, list[object]]:
    grouped: dict[int, list[object]] = {}
    for item in items:
        key = getattr(item, key_name, None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(item)
    return grouped


def first_by_id(items: list[object]) -> dict[int, object]:
    return {int(item.id): item for item in items}



def build_site_nav(*, home: bool, lang: str, variant: str = "console") -> list[dict[str, str]]:
    if home:
        return [
            {"href": "#start", "label": pick_lang(lang, "开始", "Home base")},
            {"href": "#handoff", "label": pick_lang(lang, "交接", "Handoff")},
            {"href": "#console", "label": pick_lang(lang, "维护台", "Console")},
        ]
    if variant == "library":
        return [
            {"href": with_lang("/", lang), "label": pick_lang(lang, "首页", "Home")},
            {"href": with_lang("/library", lang), "label": pick_lang(lang, "对象库", "Library")},
            {"href": with_lang("/access", lang), "label": pick_lang(lang, "访问", "Access")},
            {"href": with_lang("/shares", lang), "label": pick_lang(lang, "分享", "Shares")},
            {"href": with_lang("/activity", lang), "label": pick_lang(lang, "活动", "Activity")},
            {"href": with_lang("/settings", lang), "label": pick_lang(lang, "设置", "Settings")},
        ]
    return [
        {"href": with_lang("/", lang), "label": pick_lang(lang, "首页", "Home")},
        {"href": with_lang("/library", lang), "label": pick_lang(lang, "对象库", "Library")},
        {"href": with_lang("/access", lang), "label": pick_lang(lang, "访问", "Access")},
        {"href": with_lang("/shares", lang), "label": pick_lang(lang, "分享", "Shares")},
        {"href": with_lang("/activity", lang), "label": pick_lang(lang, "活动", "Activity")},
        {"href": with_lang("/settings", lang), "label": pick_lang(lang, "设置", "Settings")},
    ]


__all__ = [
    "build_site_nav",
    "first_by_id",
    "group_by",
]

def _build_exposure_policy() -> dict[str, dict[str, Any]]:
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


def _derive_exposure_action_state(
    *,
    exposure: object,
    review_case_state: str,
) -> dict[str, object]:
    state = str(getattr(exposure, "state", "") or "").strip().lower()
    review_requirement = str(
        getattr(exposure, "review_requirement", "") or ""
    ).strip().lower()

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
