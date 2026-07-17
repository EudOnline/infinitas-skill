from __future__ import annotations

from typing import Any

from server.i18n import pick_lang, with_lang


def group_by(items: list[Any], key_name: str) -> dict[int, list[Any]]:
    grouped: dict[int, list[Any]] = {}
    for item in items:
        key = getattr(item, key_name, None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(item)
    return grouped


def first_by_id(items: list[Any]) -> dict[int, Any]:
    return {int(item.id): item for item in items}


def build_site_nav(*, home: bool, lang: str) -> list[dict[str, str]]:
    if home:
        return [
            {"href": "#start", "label": pick_lang(lang, "开始", "Home base")},
            {"href": "#handoff", "label": pick_lang(lang, "交接", "Handoff")},
            {"href": "#console", "label": pick_lang(lang, "维护台", "Console")},
        ]
    return [
        {"href": with_lang("/", lang), "label": pick_lang(lang, "首页", "Home")},
        {"href": with_lang("/profile", lang), "label": pick_lang(lang, "档案", "Profile")},
        {"href": with_lang("/manage", lang), "label": pick_lang(lang, "管理", "Management")},
    ]


__all__ = [
    "build_site_nav",
    "first_by_id",
    "group_by",
]
