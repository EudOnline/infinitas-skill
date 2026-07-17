from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from server import __version__ as server_version
from server.i18n import pick_lang, resolve_language, with_lang
from server.modules.shared.json import read_json_file as _read_json
from server.ui.formatting import build_kawaii_ui_context, localized_stamp
from server.ui.navigation import build_site_nav
from server.ui.queries import get_dashboard_counts, get_user_stats


def _catalog_payload(settings: Any, name: str) -> dict:
    for root in (settings.artifact_path,):
        payload = _read_json(root / name)
        if payload:
            return payload
    return {}


def _get_skill_icon(skill: dict[str, Any]) -> str:
    name = skill.get("name", "").lower()
    tags = [tag.lower() for tag in skill.get("tags", [])]

    if "discovery" in tags or "search" in tags:
        return "🔍"
    if "install" in tags or "pull" in tags:
        return "📦"
    if "release" in tags or "publish" in tags:
        return "🚀"
    if "operate" in tags or "manage" in tags:
        return "🔧"
    if "security" in tags or "check" in tags:
        return "🔒"
    if "consume" in name:
        return "🎯"
    if "federation" in name:
        return "🌐"
    return "🎯"


def _calculate_skill_rating(skill: dict[str, Any]) -> float | None:
    review_state = skill.get("review_state", "")
    approval_count = skill.get("approval_count", 0)

    if review_state == "approved" and approval_count > 0:
        base = 4.8 if approval_count >= 2 else 4.5
        return round(base, 1)
    return None


def _featured_skills(discovery_payload: dict, lang: str) -> list[dict[str, Any]]:
    featured_skills = []
    for skill in (discovery_payload.get("skills") or [])[:3]:
        publisher = skill.get("publisher") or ""
        name = skill.get("name") or ""
        qualified_name = f"{publisher}/{name}" if publisher and name else name
        summary = skill.get("summary") or pick_lang(
            lang,
            "查看信任状态、版本和安装建议。",
            "Review trust, version, and install guidance.",
        )
        if len(summary) > 96:
            summary = summary[:93].rstrip() + "..."
        featured_skills.append(
            {
                "name": name or qualified_name or pick_lang(lang, "未命名 skill", "Unnamed skill"),
                "qualified_name": qualified_name,
                "publisher": publisher,
                "version": skill.get("version") or "active",
                "summary": summary,
                "icon": _get_skill_icon(skill),
                "rating": _calculate_skill_rating(skill),
                "inspect_command": f"uv run infinitas discovery inspect {qualified_name} --json"
                if qualified_name
                else "",
            }
        )
    return featured_skills


def _operating_states(
    lang: str, lifecycle_mode: str, generated_at: str | None, counts: Any
) -> list[dict[str, Any]]:
    return [
        {
            "icon": "🔒",
            "label": pick_lang(lang, "模式", "Mode"),
            "value": lifecycle_mode,
            "detail": "",
        },
        {
            "icon": "📅",
            "label": pick_lang(lang, "同步", "Sync"),
            "value": localized_stamp(generated_at, lang),
            "detail": "",
        },
        {
            "icon": "⚡",
            "label": pick_lang(lang, "流转", "Flow"),
            "value": (
                f"{counts.pending_reviews} 审核 / {counts.queued_jobs} 待处理"
                if lang == "zh"
                else f"{counts.pending_reviews} review / {counts.queued_jobs} pending"
            ),
            "detail": (
                f"{counts.running_jobs} 运行中"
                if lang == "zh"
                else f"{counts.running_jobs} running"
            ),
        },
    ]


def _handoff_examples(
    lang: str, inspect_target: str
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    commands = [
        {
            "label": pick_lang(lang, "执行命令", "Run command"),
            "title": pick_lang(lang, "搜索候选", "Search options"),
            "short_label": pick_lang(lang, "搜索", "Search"),
            "command": (
                "uv run infinitas discovery recommend "
                '"Need a codex skill for repository operations" --target-agent codex --json'
            ),
        },
        {
            "label": pick_lang(lang, "执行命令", "Run command"),
            "title": pick_lang(lang, "检查细节", "Inspect details"),
            "short_label": pick_lang(lang, "检查", "Inspect"),
            "command": f"uv run infinitas discovery inspect {inspect_target} --json",
        },
    ]
    prompts = [
        {
            "label": pick_lang(lang, "交任务", "Delegate"),
            "title": pick_lang(lang, "找 skill，再给步骤", "Find a skill, then outline steps"),
            "short_label": pick_lang(lang, "找 skill", "Find skill"),
            "prompt": pick_lang(
                lang,
                "帮我在私有技能仓库里找适合做 registry 运维的 skill，先说明风险，再给安装步骤。",
                "Help me find a skill for registry operations in the private catalog, explain the risks first, then give me the install steps.",
            ),
        },
        {
            "label": pick_lang(lang, "交任务", "Delegate"),
            "title": pick_lang(lang, "先检查，再安装", "Inspect first, then install"),
            "short_label": pick_lang(lang, "先检查", "Inspect first"),
            "prompt": pick_lang(
                lang,
                "我需要做 immutable install。先检查来源和版本，再告诉我应该安装哪一个。",
                "I need to do an immutable install. Inspect the source and version first, then tell me which one I should install.",
            ),
        },
    ]
    return commands, prompts


def _console_links(lang: str, counts: Any, settings: Any) -> list[dict[str, str]]:
    definitions = (
        ("/manage", "📚", "对象库", "Library", counts.total_objects, ""),
        ("/manage", "🚀", "发布", "Releases", counts.total_releases, ""),
        ("/manage#shares", "🔗", "分享链接", "Share Links", counts.total_share_links, ""),
        ("/manage#tokens", "🗝️", "访问", "Access", counts.total_access, ""),
        (
            "/manage#activity",
            "📋",
            "活动",
            "Activity",
            counts.pending_reviews + counts.queued_jobs + counts.running_jobs,
            "",
        ),
        ("/settings", "⚙️", "设置", "Settings", settings.environment, f"v{server_version}"),
    )
    return [
        {
            "href": with_lang(href, lang),
            "icon": icon,
            "title": pick_lang(lang, zh_title, en_title),
            "value": str(value),
            "detail": detail,
        }
        for href, icon, zh_title, en_title, value, detail in definitions
    ]


def _user_stats(request: Request, db: Session) -> dict[str, int] | None:
    from server.modules.identity.auth import maybe_get_current_user

    if maybe_get_current_user(request, db) is None:
        return None
    stats = get_user_stats(db)
    return {
        "active_tokens": stats.active_tokens,
        "accessible_skills": stats.accessible_skills,
        "new_activity": stats.new_activity,
    }


def build_home_context(*, settings: Any, db: Session, request: Request) -> dict[str, Any]:
    lang = resolve_language(request)
    discovery_payload = _catalog_payload(settings, "discovery-index.json")
    featured_skills = _featured_skills(discovery_payload, lang)
    counts = get_dashboard_counts(db)
    lifecycle_mode = pick_lang(lang, "私人优先", "Private-first")
    operating_states = _operating_states(
        lang, lifecycle_mode, discovery_payload.get("generated_at"), counts
    )
    inspect_target = (
        featured_skills[0]["qualified_name"] if featured_skills else "<publisher>/<skill>"
    )
    command_examples, human_prompts = _handoff_examples(lang, inspect_target)
    console_links = _console_links(lang, counts, settings)
    stats = _user_stats(request, db)
    page_eyebrow = pick_lang(lang, "私人技能工作台", "Private agent workspace")

    context = {
        "title": pick_lang(lang, "infinitas 私人技能库", "infinitas private skill library"),
        "page_description": pick_lang(
            lang,
            "infinitas - 小二的私人技能库，覆盖技能创作、发布、分享与安装",
            "infinitas - a private-first agent skill library for authoring, release, sharing, and install",
        ),
        "page_eyebrow": page_eyebrow,
        "page_kicker": lifecycle_mode,
        "page_mode": "home",
        "nav_links": build_site_nav(home=True, lang=lang),
        "hero_title": pick_lang(lang, "交给 Agent", "Hand it to Agent"),
        "hero_emphasis": "",
        "hero_body": pick_lang(
            lang,
            "搜索、检查、执行，交给 Agent 完成。",
            "Search, inspect, and execute — let the Agent handle it.",
        ),
        "hero_primary_link": {
            "href": "#handoff",
            "label": pick_lang(lang, "复制任务提示", "Copy task prompt"),
        },
        "hero_primary_copy": human_prompts[0]["prompt"] if human_prompts else "",
        "operating_states": operating_states,
        "human_prompts": human_prompts,
        "command_examples": command_examples,
        "console_links": console_links,
        "featured_skills": featured_skills,
        "maintainer_primary_link": {
            "href": with_lang("/manage", lang),
            "label": pick_lang(lang, "打开对象库", "Open Library"),
        },
        "maintainer_body": pick_lang(
            lang,
            "",
            "",
        ),
        "registry_reader_tokens_enabled": bool(settings.registry_read_tokens),
        "stats": stats,
    }
    context.update(build_kawaii_ui_context(request, lang, lifecycle_mode, page_eyebrow))
    return context
