from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.models import (
    AccessGrant,
    Credential,
    Exposure,
    Job,
    Release,
    ReviewCase,
    Skill,
    SkillDraft,
)
from server.ui.formatting import build_kawaii_ui_context, localized_stamp
from server.ui.i18n import pick_lang, resolve_language, with_lang
from server.ui.navigation import build_site_nav


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


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


def build_home_context(*, settings: Any, db: Session, request: Request) -> dict[str, Any]:
    lang = resolve_language(request)
    discovery_payload = _catalog_payload(settings, "discovery-index.json")
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
                "inspect_command": f"scripts/inspect-skill.sh {qualified_name}"
                if qualified_name
                else "",
            }
        )

    total_skills = int(db.scalar(select(func.count()).select_from(Skill)) or 0)
    total_drafts = int(db.scalar(select(func.count()).select_from(SkillDraft)) or 0)
    total_releases = int(db.scalar(select(func.count()).select_from(Release)) or 0)
    total_exposures = int(db.scalar(select(func.count()).select_from(Exposure)) or 0)
    total_access = int(db.scalar(select(func.count()).select_from(Credential)) or 0) + int(
        db.scalar(select(func.count()).select_from(AccessGrant)) or 0
    )
    pending_reviews = int(
        db.scalar(select(func.count()).select_from(ReviewCase).where(ReviewCase.state == "open"))
        or 0
    )
    queued_jobs = int(
        db.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) or 0
    )
    running_jobs = int(
        db.scalar(select(func.count()).select_from(Job).where(Job.status == "running")) or 0
    )

    lifecycle_mode = pick_lang(lang, "私人优先", "Private-first")
    operating_states = [
        {
            "icon": "🔒",
            "label": pick_lang(lang, "模式", "Mode"),
            "value": lifecycle_mode,
            "detail": pick_lang(
                lang, "私人直达，公开必须审核", "Private flows directly, public requires review"
            ),
        },
        {
            "icon": "📅",
            "label": pick_lang(lang, "同步", "Sync"),
            "value": localized_stamp(discovery_payload.get("generated_at"), lang),
            "detail": pick_lang(lang, "catalog 快照", "Catalog snapshot"),
        },
        {
            "icon": "⚡",
            "label": pick_lang(lang, "流转", "Flow"),
            "value": (
                f"{pending_reviews} 审核单 / {queued_jobs} 待物化"
                if lang == "zh"
                else f"{pending_reviews} review cases / {queued_jobs} materializations pending"
            ),
            "detail": f"{running_jobs} 物化中" if lang == "zh" else f"{running_jobs} materializing",
        },
    ]
    inspect_example_target = featured_skills[0]["qualified_name"] if featured_skills else "<publisher>/<skill>"
    command_examples = [
        {
            "label": pick_lang(lang, "执行命令", "Run command"),
            "title": pick_lang(lang, "搜索候选", "Search options"),
            "short_label": pick_lang(lang, "搜索", "Search"),
            "command": 'scripts/recommend-skill.sh "Need a codex skill for repository operations"',
        },
        {
            "label": pick_lang(lang, "执行命令", "Run command"),
            "title": pick_lang(lang, "检查细节", "Inspect details"),
            "short_label": pick_lang(lang, "检查", "Inspect"),
            "command": f"scripts/inspect-skill.sh {inspect_example_target}",
        },
    ]
    human_prompts = [
        {
            "label": pick_lang(lang, "交任务", "Delegate"),
            "title": pick_lang(lang, "找 skill，再给步骤", "Find a skill, then outline steps"),
            "short_label": pick_lang(lang, "找 skill", "Find skill"),
            "prompt": (
                "帮我在私有技能仓库里找适合做 registry 运维的 skill，先说明风险，再给安装步骤。"
                if lang == "zh"
                else "Help me find a skill for registry operations in the private catalog, explain the risks first, then give me the install steps."
            ),
        },
        {
            "label": pick_lang(lang, "交任务", "Delegate"),
            "title": pick_lang(lang, "先检查，再安装", "Inspect first, then install"),
            "short_label": pick_lang(lang, "先检查", "Inspect first"),
            "prompt": (
                "我需要做 immutable install。先检查来源和版本，再告诉我应该安装哪一个。"
                if lang == "zh"
                else "I need to do an immutable install. Inspect the source and version first, then tell me which one I should install."
            ),
        },
    ]
    human_input_fields = (
        ["目标", "安装位置", "风险偏好"] if lang == "zh" else ["Goal", "Install path", "Risk level"]
    )
    console_links = [
        {
            "href": with_lang("/skills", lang),
            "icon": "📦",
            "title": pick_lang(lang, "技能", "Skills"),
            "value": str(total_skills),
            "detail": pick_lang(lang, "命名空间中的技能", "Skill records in the namespace"),
        },
        {
            "href": with_lang("/skills#drafts", lang),
            "icon": "✨",
            "title": pick_lang(lang, "草稿", "Drafts"),
            "value": str(total_drafts),
            "detail": pick_lang(lang, "可继续编辑", "Still editable"),
        },
        {
            "href": with_lang("/skills#releases", lang),
            "icon": "⚙️",
            "title": pick_lang(lang, "发布", "Releases"),
            "value": str(total_releases),
            "detail": pick_lang(lang, "不可变产物", "Immutable delivery units"),
        },
        {
            "href": with_lang("/skills#share", lang),
            "icon": "🌐",
            "title": pick_lang(lang, "分享", "Share"),
            "value": str(total_exposures),
            "detail": pick_lang(lang, "私人、令牌和公开出口", "Private, token, and public exits"),
        },
        {
            "href": with_lang("/access/tokens", lang),
            "icon": "🗝️",
            "title": pick_lang(lang, "访问", "Access"),
            "value": str(total_access),
            "detail": pick_lang(lang, "令牌与授权记录", "Tokens and grant records"),
        },
        {
            "href": with_lang("/review-cases", lang),
            "icon": "📝",
            "title": pick_lang(lang, "审核", "Review"),
            "value": str(pending_reviews),
            "detail": pick_lang(lang, "公开出口审核单", "Public exposure review cases"),
        },
    ]
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
            "这里是你的私人技能库，搜索、检查和执行都交给它。",
            "This private skill library lets the agent search, inspect, and execute for you.",
        ),
        "hero_support": pick_lang(
            lang,
            "你只要说明目标、位置和风险，它会沿着技能生命周期继续推进。",
            "You only need to name the goal, location, and risk level, then it moves through the skill lifecycle.",
        ),
        "hero_primary_link": {
            "href": "#handoff",
            "label": pick_lang(lang, "复制任务提示", "Copy task prompt"),
        },
        "hero_secondary_link": {
            "href": "#console",
            "label": pick_lang(lang, "查看维护台", "Open console"),
        },
        "hero_primary_copy": human_prompts[0]["prompt"] if human_prompts else "",
        "operating_states": operating_states,
        "human_input_fields": human_input_fields,
        "human_prompts": human_prompts,
        "command_examples": command_examples,
        "console_links": console_links,
        "featured_skills": featured_skills,
        "maintainer_primary_link": {
            "href": with_lang("/skills", lang),
            "label": pick_lang(lang, "打开维护台", "Open console"),
        },
        "maintainer_body": pick_lang(
            lang,
            "维护台现在完全围绕技能、草稿、发布、分享、访问和审核，不再经过旧的 submission 队列。",
            "The console now centers on skills, drafts, releases, sharing, access, and review without routing work through legacy submission queues.",
        ),
        "registry_reader_tokens_enabled": bool(settings.registry_read_tokens),
    }
    context.update(build_kawaii_ui_context(request, lang, lifecycle_mode, page_eyebrow))
    return context
