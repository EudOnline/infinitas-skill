from __future__ import annotations

import json
from datetime import datetime

from fastapi import Request

from server.i18n import build_language_switches, load_locale, pick_lang, t, with_lang
from server.modules.shared.formatting import (
    humanize_identifier,
    humanize_timestamp,
)
from server.modules.shared.json import loads_json_object as load_json_object


def load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def short_stamp(value: str | None) -> str:
    if not value:
        return "No snapshot"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return value


def localized_stamp(value: str | None, lang: str) -> str:
    if not value:
        return t(lang, "localized_stamp_fallback")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return value


def _humanize_with_mapping(
    value: str | None,
    lang: str,
    mapping: dict[str, tuple[str, str]],
) -> str:
    labels = mapping.get((value or "").strip().lower())
    if labels is not None:
        return pick_lang(lang, labels[0], labels[1])
    return humanize_identifier(value)


def humanize_status(status: str | None, lang: str) -> str:
    return _humanize_with_mapping(status, lang, {})


def humanize_job_kind(kind: str | None, lang: str) -> str:
    return _humanize_with_mapping(
        kind,
        lang,
        {"materialize_release": ("生成发布产物", "Materialize release")},
    )


def humanize_role(role: str | None, lang: str) -> str:
    return _humanize_with_mapping(role, lang, {})


def _ui_translations(lang: str) -> dict[str, str]:
    ui = {**load_locale("en"), **load_locale(lang)}
    ui["search_create_command"] = (
        'uv run infinitas registry skills create --slug my-skill --display-name "My Skill"'
    )
    return ui


def build_kawaii_ui_context(
    request: Request,
    lang: str,
    page_kicker: str,
    page_eyebrow: str,
) -> dict:
    ui = _ui_translations(lang)
    ui["page_kicker"] = page_kicker
    ui["page_eyebrow"] = page_eyebrow
    return {
        "page_language": lang,
        "page_lang_attr": "zh-CN" if lang == "zh" else "en",
        "home_href": with_lang("/", lang),
        "session_ui": {},
        "language_switches": build_language_switches(request, lang),
        "theme_switches": [
            {"value": "light", "label": t(lang, "theme.light")},
            {"value": "dark", "label": t(lang, "theme.dark")},
        ],
        "ui": ui,
    }


__all__ = [
    "build_kawaii_ui_context",
    "humanize_identifier",
    "humanize_job_kind",
    "humanize_role",
    "humanize_status",
    "humanize_timestamp",
    "load_json_list",
    "load_json_object",
    "localized_stamp",
    "short_stamp",
]
