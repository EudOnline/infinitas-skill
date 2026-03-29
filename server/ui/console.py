from __future__ import annotations

from typing import Any, Callable

from fastapi import Request

from server.models import User


ResolveLanguage = Callable[[Request], str]
PickLang = Callable[[str, str, str], str]
HumanizeRole = Callable[[str | None, str], str]
HumanizeStatus = Callable[[str | None, str], str]
HumanizeJobKind = Callable[[str | None, str], str]
HumanizeTimestamp = Callable[[str | None], str]
BuildKawaiiUIContext = Callable[[Request, str, str, str], dict[str, Any]]
BuildSiteNav = Callable[..., list[dict[str, str]]]
WithLang = Callable[[str, str], str]


def build_console_context(
    *,
    request: Request,
    title: str,
    content: str,
    limit: int,
    items: list[dict[str, Any]],
    cli_command: str,
    stats: list[dict[str, str]],
    insight_cards: list[dict[str, str]] | None = None,
    show_console_session: bool = True,
    nav_links: list[dict[str, str]] | None = None,
    resolve_language: ResolveLanguage,
    pick_lang: PickLang,
    build_kawaii_ui_context: BuildKawaiiUIContext,
    humanize_status: HumanizeStatus,
    humanize_job_kind: HumanizeJobKind,
    humanize_timestamp: HumanizeTimestamp,
    build_site_nav: BuildSiteNav,
    with_lang: WithLang,
) -> dict[str, Any]:
    lang = resolve_language(request)
    page_eyebrow = pick_lang(lang, "维护控制台", "Maintainer-only console")
    page_kicker = pick_lang(lang, "维护模式", "Maintainer mode")
    context = {
        "request": request,
        "title": title,
        "content": content,
        "page_eyebrow": page_eyebrow,
        "page_kicker": page_kicker,
        "page_mode": "console",
        "nav_links": nav_links or build_site_nav(home=False, lang=lang, pick_lang=pick_lang, with_lang=with_lang),
        "items": items,
        "limit": limit,
        "cli_command": cli_command,
        "page_stats": stats,
        "insight_cards": insight_cards or [],
        "show_console_session": show_console_session,
        "format_status": lambda value: humanize_status(value, lang),
        "format_job_kind": lambda value: humanize_job_kind(value, lang),
        "format_timestamp": humanize_timestamp,
    }
    context.update(build_kawaii_ui_context(request, lang, page_kicker, page_eyebrow))
    return context


def build_console_forbidden_context(
    *,
    request: Request,
    user: User,
    allowed_roles: tuple[str, ...],
    resolve_language: ResolveLanguage,
    pick_lang: PickLang,
    humanize_role: HumanizeRole,
    with_lang: WithLang,
    build_console_context_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    lang = resolve_language(request)
    allowed_text = ", ".join(humanize_role(role, lang) for role in allowed_roles) or pick_lang(
        lang,
        "维护者",
        "Maintainer",
    )
    context = build_console_context_fn(
        request=request,
        title=pick_lang(lang, "维护台访问受限", "Console access denied"),
        content=pick_lang(
            lang,
            f"当前账号角色是{humanize_role(user.role, lang)}，此页面仅允许{allowed_text}访问。",
            f"Your current role is {humanize_role(user.role, lang)}. This page is limited to {allowed_text}.",
        ),
        limit=0,
        items=[],
        cli_command="",
        stats=[],
        insight_cards=[],
        show_console_session=True,
    )
    context.update(
        {
            "page_kicker": pick_lang(lang, "访问受限", "Access limited"),
            "page_eyebrow": pick_lang(lang, "受限控制台", "Protected console"),
            "denied_title": pick_lang(lang, "维护台访问受限", "Console access denied"),
            "denied_body": pick_lang(
                lang,
                f"需要{allowed_text}权限才能继续访问维护台。你可以先返回首页，或者切换到有权限的账号。",
                f"Maintainer role required before you can continue into the console. Head back home or switch to an authorized account.",
            ),
            "denied_home_href": with_lang("/", lang),
            "denied_home_label": pick_lang(lang, "返回首页", "Back home"),
        }
    )
    if isinstance(context.get("ui"), dict):
        context["ui"]["page_kicker"] = context["page_kicker"]
        context["ui"]["page_eyebrow"] = context["page_eyebrow"]
    return context


def build_lifecycle_console_context(
    *,
    request: Request,
    title: str,
    content: str,
    limit: int,
    items: list[dict[str, Any]],
    cli_command: str,
    stats: list[dict[str, str]],
    insight_cards: list[dict[str, str]] | None = None,
    resolve_language: ResolveLanguage,
    pick_lang: PickLang,
    build_console_context_fn: Callable[..., dict[str, Any]],
    build_site_nav: BuildSiteNav,
    with_lang: WithLang,
) -> dict[str, Any]:
    lang = resolve_language(request)
    return build_console_context_fn(
        request=request,
        title=title,
        content=content,
        limit=limit,
        items=items,
        cli_command=cli_command,
        stats=stats,
        insight_cards=insight_cards,
        nav_links=build_site_nav(home=False, lang=lang, pick_lang=pick_lang, with_lang=with_lang),
    )
