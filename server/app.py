from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.api.auth import router as auth_router
from server.api.background import router as background_router
from server.api.search import router as search_router
from server.auth import (
    AUTH_COOKIE_NAME,
    get_current_user,
    maybe_get_current_access_context,
    maybe_get_current_user,
)
from server.db import ensure_database_ready, get_db
from server.modules.access.router import router as access_router
from server.modules.authoring.router import router as authoring_router
from server.modules.discovery.router import router as discovery_router
from server.modules.exposure.router import router as exposure_router
from server.modules.registry.router import router as registry_router
from server.modules.release.router import router as release_router
from server.modules.review.router import router as review_router
from server.models import (
    AccessGrant,
    Artifact,
    Credential,
    Exposure,
    Job,
    Principal,
    Release,
    ReviewCase,
    Skill,
    SkillDraft,
    SkillVersion,
    User,
)
from server.settings import get_settings
from server.ui import (
    build_console_context as build_console_ui_context,
    build_console_forbidden_context as build_console_forbidden_ui_context,
    build_home_context as build_home_ui_context,
    build_lifecycle_console_context as build_lifecycle_console_ui_context,
    build_site_nav as build_site_nav_links,
)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load_json_object(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def _catalog_payload(settings, name: str) -> dict:
    for root in (settings.artifact_path, settings.root_dir / 'catalog'):
        payload = _read_json(root / name)
        if payload:
            return payload
    return {}


def _get_skill_icon(skill: dict) -> str:
    """Get emoji icon based on skill tags/name"""
    name = skill.get('name', '').lower()
    tags = [t.lower() for t in skill.get('tags', [])]
    
    if 'discovery' in tags or 'search' in tags:
        return '🔍'
    if 'install' in tags or 'pull' in tags:
        return '📦'
    if 'release' in tags or 'publish' in tags:
        return '🚀'
    if 'operate' in tags or 'manage' in tags:
        return '🔧'
    if 'security' in tags or 'check' in tags:
        return '🔒'
    if 'consume' in name:
        return '🎯'
    if 'federation' in name:
        return '🌐'
    
    return '🎯'


def _calculate_skill_rating(skill: dict) -> float | None:
    """Calculate skill rating based on review state"""
    review_state = skill.get('review_state', '')
    approval_count = skill.get('approval_count', 0)
    
    if review_state == 'approved' and approval_count > 0:
        base = 4.5
        if approval_count >= 2:
            base = 4.8
        return round(base, 1)
    return None


def _short_stamp(value: str | None) -> str:
    if not value:
        return 'No snapshot'
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except ValueError:
        return value


def _pick_lang(lang: str, zh: str, en: str) -> str:
    return zh if lang == 'zh' else en


def _humanize_identifier(value: str | None) -> str:
    if not value:
        return '-'
    return value.replace('_', ' ').replace('-', ' ').strip().title()


def _humanize_status(status: str | None, lang: str) -> str:
    mapping = {
        'draft': ('草稿', 'Draft'),
        'open': ('打开', 'Open'),
        'sealed': ('已封版', 'Sealed'),
        'ready': ('已就绪', 'Ready'),
        'active': ('已生效', 'Active'),
        'revoked': ('已撤销', 'Revoked'),
        'pending_policy': ('等待策略', 'Pending policy'),
        'review_open': ('审核进行中', 'Review open'),
        'validation_requested': ('等待校验', 'Waiting validation'),
        'review_requested': ('待评审', 'Waiting review'),
        'approved': ('已批准', 'Approved'),
        'rejected': ('已驳回', 'Rejected'),
        'validated': ('已校验', 'Validated'),
        'promoted': ('已提升', 'Promoted'),
        'published': ('已发布', 'Published'),
        'pending': ('待处理', 'Pending'),
        'queued': ('排队中', 'Queued'),
        'running': ('运行中', 'Running'),
        'completed': ('已完成', 'Completed'),
        'failed': ('失败', 'Failed'),
    }
    labels = mapping.get((status or '').strip().lower())
    if labels is not None:
        return _pick_lang(lang, labels[0], labels[1])
    return _humanize_identifier(status)


def _humanize_job_kind(kind: str | None, lang: str) -> str:
    mapping = {
        'materialize_release': ('生成发布产物', 'Materialize release'),
    }
    labels = mapping.get((kind or '').strip().lower())
    if labels is not None:
        return _pick_lang(lang, labels[0], labels[1])
    return _humanize_identifier(kind)


def _humanize_role(role: str | None, lang: str) -> str:
    mapping = {
        'maintainer': ('维护者', 'Maintainer'),
        'contributor': ('贡献者', 'Contributor'),
    }
    labels = mapping.get((role or '').strip().lower())
    if labels is not None:
        return _pick_lang(lang, labels[0], labels[1])
    return _humanize_identifier(role)


def _humanize_audience_type(audience_type: str | None, lang: str) -> str:
    mapping = {
        'private': ('私人', 'Private'),
        'grant': ('令牌共享', 'Shared by token'),
        'public': ('公开', 'Public'),
    }
    labels = mapping.get((audience_type or '').strip().lower())
    if labels is not None:
        return _pick_lang(lang, labels[0], labels[1])
    return _humanize_identifier(audience_type)


def _humanize_listing_mode(listing_mode: str | None, lang: str) -> str:
    mapping = {
        'listed': ('可列出', 'Listed'),
        'direct_only': ('仅直达', 'Direct only'),
    }
    labels = mapping.get((listing_mode or '').strip().lower())
    if labels is not None:
        return _pick_lang(lang, labels[0], labels[1])
    return _humanize_identifier(listing_mode)


def _humanize_install_mode(install_mode: str | None, lang: str) -> str:
    mapping = {
        'enabled': ('允许安装', 'Install enabled'),
        'disabled': ('禁止安装', 'Install disabled'),
    }
    labels = mapping.get((install_mode or '').strip().lower())
    if labels is not None:
        return _pick_lang(lang, labels[0], labels[1])
    return _humanize_identifier(install_mode)


def _humanize_review_gate(review_gate: str | None, lang: str) -> str:
    mapping = {
        'none': ('无需审核', 'No review'),
        'advisory': ('建议审核', 'Advisory review'),
        'blocking': ('阻塞审核', 'Blocking review'),
        'open': ('待审核', 'Open'),
        'approved': ('已通过', 'Approved'),
        'rejected': ('已拒绝', 'Rejected'),
    }
    labels = mapping.get((review_gate or '').strip().lower())
    if labels is not None:
        return _pick_lang(lang, labels[0], labels[1])
    return _humanize_identifier(review_gate)


def _humanize_timestamp(value: str | None) -> str:
    if not value:
        return '-'
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return value
    stamp = parsed.strftime('%Y-%m-%d %H:%M')
    if parsed.tzinfo is not None and parsed.utcoffset() is not None:
        stamp = f'{stamp} UTC'
    return stamp


def _with_lang(href: str, lang: str) -> str:
    if not href or href.startswith('#'):
        return href
    parts = urlsplit(href)
    if parts.scheme or parts.netloc:
        return href
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query['lang'] = lang
    return urlunsplit(('', '', parts.path or '/', urlencode(query), parts.fragment))


def _resolve_language(request: Request) -> str:
    lang = (request.query_params.get('lang') or 'zh').strip().lower()
    return 'en' if lang.startswith('en') else 'zh'


def _request_path_with_query(request: Request) -> str:
    path = request.url.path or '/'
    query = request.url.query
    if query:
        return f'{path}?{query}'
    return path


def _build_auth_redirect_url(request: Request, lang: str) -> str:
    target_parts = urlsplit(_with_lang('/', lang))
    query = dict(parse_qsl(target_parts.query, keep_blank_values=True))
    query['auth'] = 'required'
    query['next'] = _request_path_with_query(request)
    return urlunsplit(('', '', target_parts.path or '/', urlencode(query), target_parts.fragment))


def _localized_stamp(value: str | None, lang: str) -> str:
    if not value:
        return _pick_lang(lang, '暂无快照', 'No snapshot')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except ValueError:
        return value


def _build_language_switches(request: Request, lang: str) -> list[dict[str, str | bool]]:
    options = [('zh', '中'), ('en', 'EN')]
    return [
        {
            'code': code,
            'label': label,
            'href': str(request.url.include_query_params(lang=code)),
            'active': code == lang,
        }
        for code, label in options
    ]


def _build_kawaii_ui_context(request: Request, lang: str, page_kicker: str, page_eyebrow: str) -> dict:
    return {
        'page_language': lang,
        'page_lang_attr': 'zh-CN' if lang == 'zh' else 'en',
        'home_href': _with_lang('/', lang),
        'session_ui': {
            'has_auth_cookie_hint': bool(request.cookies.get(AUTH_COOKIE_NAME)),
        },
        'language_switches': _build_language_switches(request, lang),
        'theme_switches': [
            {'value': 'light', 'label': _pick_lang(lang, '浅色', 'Light')},
            {'value': 'dark', 'label': _pick_lang(lang, '深色', 'Dark')},
        ],
        'ui': {
            'brand_subtitle': _pick_lang(lang, '私人技能库', 'Private skill library'),
            'theme_toggle_label': _pick_lang(lang, '主题切换', 'Theme switcher'),
            'language_toggle_label': _pick_lang(lang, '语言切换', 'Language switcher'),
            'copy_success': _pick_lang(lang, '已复制', 'Copied'),
            'copy_error': _pick_lang(lang, '复制失败', 'Copy failed'),
            'toast_close': _pick_lang(lang, '关闭提示', 'Dismiss notification'),
            'copy_icon_title': _pick_lang(lang, '复制', 'Copy'),
            'copy_button_label': _pick_lang(lang, '复制', 'Copy'),
            'status_running': _pick_lang(lang, '运行中', 'Running'),
            'search_placeholder': _pick_lang(lang, '搜索技能或命令', 'Search skills or commands'),
            'search_results_label': _pick_lang(lang, '搜索结果', 'Search results'),
            'search_skills_label': _pick_lang(lang, '技能', 'Skills'),
            'search_commands_label': _pick_lang(lang, '命令', 'Commands'),
            'search_empty_label': _pick_lang(lang, '未找到匹配结果', 'No matching results'),
            'search_create_label': _pick_lang(lang, '创建新技能', 'Create skill'),
            'search_create_command': 'scripts/new-skill.sh lvxiaoer/my-skill basic',
            'search_auth_required': _pick_lang(lang, '请先登录后搜索私人技能库', 'Sign in to search the private-first library'),
            'page_kicker': page_kicker,
            'page_eyebrow': page_eyebrow,
            'handoff_title': _pick_lang(lang, '交接台', 'Hand-off desk'),
            'handoff_human_tab': _pick_lang(lang, '交任务', 'Delegate'),
            'handoff_agent_tab': _pick_lang(lang, '执行命令', 'Run command'),
            'copy_prompt_action': _pick_lang(lang, '复制这条提示', 'Copy this prompt'),
            'cli_mirror_label': _pick_lang(lang, '命令镜像', 'CLI mirror'),
            'console_section_title': _pick_lang(lang, '有事再进维护台', 'Open console when needed'),
            'skills_section_title': _pick_lang(lang, '常用技能', 'Popular skills'),
            'skills_section_subtitle': _pick_lang(
                lang,
                '从目录里挑 3 个入口，先检查再交给 Agent。',
                'Pick 3 likely entries, inspect first, then hand them off.',
            ),
            'featured_skill_fallback': _pick_lang(lang, '精选', 'Featured'),
            'copy_inspect_action': _pick_lang(lang, '复制检查命令', 'Copy inspect command'),
            'go_handoff_action': _pick_lang(lang, '去交接台', 'Go to hand-off'),
            'quick_start_title': _pick_lang(lang, '快速开始', 'Quick start'),
            'quick_start_hint': _pick_lang(lang, '点击复制，粘贴到 Agent 对话框使用', 'Tap to copy and paste into your Agent chat'),
            'auth_modal_title': _pick_lang(lang, '身份认证', 'Identity check'),
            'auth_modal_desc': _pick_lang(lang, '请输入访问令牌以解锁个性化设置', 'Enter your access token to unlock personalized settings'),
            'auth_modal_placeholder': _pick_lang(lang, '输入你的访问令牌', 'Enter your access token'),
            'auth_modal_hint': _pick_lang(lang, '访问令牌有效期 30 天', 'Token stays valid for 30 days'),
            'auth_invalid': _pick_lang(lang, '访问令牌无效', 'Invalid token'),
            'auth_cancel': _pick_lang(lang, '取消', 'Cancel'),
            'auth_close': _pick_lang(lang, '关闭', 'Close'),
            'auth_verify': _pick_lang(lang, '验证', 'Verify'),
            'auth_verify_loading': _pick_lang(lang, '验证中...', 'Verifying...'),
            'auth_login': _pick_lang(lang, '登录', 'Login'),
            'auth_enter_token': _pick_lang(lang, '请输入访问令牌', 'Please enter token'),
            'auth_token_min': _pick_lang(lang, '访问令牌长度不能少于 8 位', 'Token must be at least 8 characters'),
            'auth_token_max': _pick_lang(lang, '访问令牌长度不能超过 128 位', 'Token must not exceed 128 characters'),
            'auth_invalid_characters': _pick_lang(lang, '访问令牌包含非法字符', 'Token contains invalid characters'),
            'auth_verify_failed': _pick_lang(lang, '验证失败，请检查访问令牌是否正确', 'Verification failed, please check your token'),
            'auth_network_error': _pick_lang(lang, '网络错误，请检查网络连接后重试', 'Network error, please check your connection and try again'),
            'auth_bad_server_data': _pick_lang(lang, '服务器返回无效数据', 'The server returned invalid data'),
            'auth_session_active': _pick_lang(lang, '会话已连接', 'Session active'),
            'auth_expiry_days': _pick_lang(lang, '{days} 天后过期', 'Expires in {days} days'),
            'show_password': _pick_lang(lang, '显示密码', 'Show password'),
            'hide_password': _pick_lang(lang, '隐藏密码', 'Hide password'),
            'toggle_password_visibility': _pick_lang(lang, '切换密码可见性', 'Toggle password visibility'),
            'user_panel_auth_title': _pick_lang(lang, '认证', 'Authentication'),
            'user_panel_auth_desc': _pick_lang(lang, '登录后可保存背景设置，并进入你的私人技能库', 'Sign in to sync preferences and open your private skill library'),
            'user_panel_auth_action': _pick_lang(lang, '输入访问令牌', 'Enter token'),
            'user_panel_background_label': _pick_lang(lang, '背景', 'Background'),
            'user_panel_theme_light': _pick_lang(lang, '浅色', 'Light'),
            'user_panel_theme_dark': _pick_lang(lang, '深色', 'Dark'),
            'user_panel_logout': _pick_lang(lang, '退出登录', 'Sign out'),
            'user_menu_anon_label': _pick_lang(lang, '登录', 'Sign in'),
            'user_menu_logged_label': _pick_lang(lang, '已登录用户菜单', 'Account menu'),
            'console_session_guest': _pick_lang(lang, '登录', 'Sign in'),
            'console_session_desc': _pick_lang(
                lang,
                '登录后可继续在维护台搜索、检查和处理技能生命周期。',
                'Sign in to keep searching, inspecting, and operating across the skill lifecycle.',
            ),
            'console_session_open_auth': _pick_lang(lang, '输入访问令牌', 'Enter token'),
            'console_session_label': _pick_lang(lang, '当前会话', 'Current session'),
            'console_session_role': _pick_lang(lang, '角色：{role}', 'Role: {role}'),
            'console_session_ready': _pick_lang(lang, '会话可用', 'Session ready'),
            'logout_success': _pick_lang(lang, '已退出登录', 'Signed out'),
            'role_maintainer': _pick_lang(lang, '维护者', 'Maintainer'),
            'role_contributor': _pick_lang(lang, '贡献者', 'Contributor'),
            'theme_light_name': _pick_lang(lang, '浅色主题', 'light theme'),
            'theme_dark_name': _pick_lang(lang, '深色主题', 'dark theme'),
            'theme_switched': _pick_lang(lang, '已切换到 {theme}', 'Switched to {theme}'),
            'use_skill_ready': _pick_lang(lang, '技能 {name} 已就绪，命令已复制', 'Skill {name} is ready and the command has been copied'),
            'use_skill_error': _pick_lang(lang, '使用技能失败，请重试', 'Failed to use skill, please try again'),
            'generic_action_failed': _pick_lang(lang, '操作失败，请刷新页面重试', 'Action failed, please refresh and try again'),
            'generic_unexpected_error': _pick_lang(lang, '发生错误，请刷新页面重试', 'An error occurred, please refresh and try again'),
        },
    }


def _site_nav(home: bool, lang: str) -> list[dict[str, str]]:
    return build_site_nav_links(home=home, lang=lang, pick_lang=_pick_lang, with_lang=_with_lang)


def _build_home_context(settings, db: Session, request: Request) -> dict:
    return build_home_ui_context(
        settings=settings,
        db=db,
        request=request,
        resolve_language=_resolve_language,
        pick_lang=_pick_lang,
        with_lang=_with_lang,
        localized_stamp=_localized_stamp,
        build_kawaii_ui_context=_build_kawaii_ui_context,
        catalog_payload=_catalog_payload,
        get_skill_icon=_get_skill_icon,
        calculate_skill_rating=_calculate_skill_rating,
    )


def _build_console_context(
    *,
    request: Request,
    title: str,
    content: str,
    limit: int,
    items: list[dict],
    cli_command: str,
    stats: list[dict[str, str]],
    insight_cards: list[dict[str, str]] | None = None,
    show_console_session: bool = True,
    nav_links: list[dict[str, str]] | None = None,
) -> dict:
    return build_console_ui_context(
        request=request,
        title=title,
        content=content,
        limit=limit,
        items=items,
        cli_command=cli_command,
        stats=stats,
        insight_cards=insight_cards,
        show_console_session=show_console_session,
        nav_links=nav_links,
        resolve_language=_resolve_language,
        pick_lang=_pick_lang,
        build_kawaii_ui_context=_build_kawaii_ui_context,
        humanize_status=_humanize_status,
        humanize_job_kind=_humanize_job_kind,
        humanize_timestamp=_humanize_timestamp,
        build_site_nav=build_site_nav_links,
        with_lang=_with_lang,
    )


def _build_console_forbidden_context(request: Request, user: User, *allowed_roles: str) -> dict:
    return build_console_forbidden_ui_context(
        request=request,
        user=user,
        allowed_roles=allowed_roles,
        resolve_language=_resolve_language,
        pick_lang=_pick_lang,
        humanize_role=_humanize_role,
        with_lang=_with_lang,
        build_console_context_fn=_build_console_context,
    )


def _require_console_user_or_redirect(request: Request, db: Session, *allowed_roles: str) -> User | RedirectResponse:
    user = maybe_get_current_user(request, db)
    if user is None:
        return RedirectResponse(
            url=_build_auth_redirect_url(request, _resolve_language(request)),
            status_code=303,
        )
    if user.role not in set(allowed_roles):
        raise HTTPException(status_code=403, detail='insufficient role')
    return user


def _group_by(items: list[object], key_name: str) -> dict[int, list[object]]:
    grouped: dict[int, list[object]] = {}
    for item in items:
        key = getattr(item, key_name, None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(item)
    return grouped


def _first_by_id(items: list[object]) -> dict[int, object]:
    return {int(item.id): item for item in items}


def _load_registry_scope(db: Session, *, principal_id: int | None, include_all: bool) -> dict[str, object]:
    skill_query = select(Skill).order_by(Skill.updated_at.desc(), Skill.id.desc())
    if not include_all and principal_id is not None:
        skill_query = skill_query.where(Skill.namespace_id == principal_id)
    skills = db.scalars(skill_query).all()
    skill_ids = [skill.id for skill in skills]

    drafts = []
    versions = []
    releases = []
    exposures = []
    review_cases = []
    grants = []
    credentials = []

    if skill_ids:
        drafts = db.scalars(
            select(SkillDraft)
            .where(SkillDraft.skill_id.in_(skill_ids))
            .order_by(SkillDraft.updated_at.desc(), SkillDraft.id.desc())
        ).all()
        versions = db.scalars(
            select(SkillVersion)
            .where(SkillVersion.skill_id.in_(skill_ids))
            .order_by(SkillVersion.created_at.desc(), SkillVersion.id.desc())
        ).all()

    version_ids = [version.id for version in versions]
    if version_ids:
        releases = db.scalars(
            select(Release)
            .where(Release.skill_version_id.in_(version_ids))
            .order_by(Release.created_at.desc(), Release.id.desc())
        ).all()

    release_ids = [release.id for release in releases]
    if release_ids:
        exposures = db.scalars(
            select(Exposure)
            .where(Exposure.release_id.in_(release_ids))
            .order_by(Exposure.id.desc())
        ).all()

    exposure_ids = [exposure.id for exposure in exposures]
    if exposure_ids:
        review_cases = db.scalars(
            select(ReviewCase)
            .where(ReviewCase.exposure_id.in_(exposure_ids))
            .order_by(ReviewCase.id.desc())
        ).all()
        grants = db.scalars(
            select(AccessGrant)
            .where(AccessGrant.exposure_id.in_(exposure_ids))
            .order_by(AccessGrant.id.desc())
        ).all()

    grant_ids = [grant.id for grant in grants]
    credential_query = select(Credential).order_by(Credential.created_at.desc(), Credential.id.desc())
    if include_all:
        credentials = db.scalars(credential_query).all()
    elif principal_id is not None:
        if grant_ids:
            credentials = db.scalars(
                credential_query.where(
                    (Credential.principal_id == principal_id) | (Credential.grant_id.in_(grant_ids))
                )
            ).all()
        else:
            credentials = db.scalars(credential_query.where(Credential.principal_id == principal_id)).all()

    principal_ids = {skill.namespace_id for skill in skills}
    principal_ids.update(credential.principal_id for credential in credentials if credential.principal_id is not None)
    principal_ids.update(grant.created_by_principal_id for grant in grants if grant.created_by_principal_id is not None)
    principals = []
    if principal_ids:
        principals = db.scalars(
            select(Principal)
            .where(Principal.id.in_(sorted(principal_ids)))
            .order_by(Principal.id.asc())
        ).all()

    artifacts = []
    if release_ids:
        artifacts = db.scalars(
            select(Artifact)
            .where(Artifact.release_id.in_(release_ids))
            .order_by(Artifact.created_at.desc(), Artifact.id.desc())
        ).all()

    return {
        'skills': skills,
        'drafts': drafts,
        'versions': versions,
        'releases': releases,
        'exposures': exposures,
        'review_cases': review_cases,
        'grants': grants,
        'credentials': credentials,
        'principals': principals,
        'artifacts': artifacts,
    }


def _principal_label(principal: Principal | None) -> str:
    if principal is None:
        return '-'
    return principal.display_name or principal.slug or f'principal-{principal.id}'


def _is_owner(user: User, principal_id: int | None, resource_principal_id: int | None) -> bool:
    if user.role == 'maintainer':
        return True
    if principal_id is None or resource_principal_id is None:
        return False
    return principal_id == resource_principal_id


def _build_lifecycle_console_context(
    *,
    request: Request,
    title: str,
    content: str,
    limit: int,
    items: list[dict],
    cli_command: str,
    stats: list[dict[str, str]],
    insight_cards: list[dict[str, str]] | None = None,
) -> dict:
    return build_lifecycle_console_ui_context(
        request=request,
        title=title,
        content=content,
        limit=limit,
        items=items,
        cli_command=cli_command,
        stats=stats,
        insight_cards=insight_cards,
        resolve_language=_resolve_language,
        pick_lang=_pick_lang,
        build_console_context_fn=_build_console_context,
        build_site_nav=build_site_nav_links,
        with_lang=_with_lang,
    )


def _require_lifecycle_actor(
    request: Request,
    db: Session,
    *allowed_roles: str,
) -> object:
    context = maybe_get_current_access_context(request, db)
    if context is None or context.user is None:
        return RedirectResponse(
            url=_build_auth_redirect_url(request, _resolve_language(request)),
            status_code=303,
        )
    if allowed_roles and context.user.role not in set(allowed_roles):
        return _build_console_forbidden_context(request, context.user, *allowed_roles)
    return context


def create_app() -> FastAPI:
    settings = get_settings()
    templates = Jinja2Templates(directory=str(settings.template_dir))
    ensure_database_ready()
    app = FastAPI(title='infinitas hosted registry')
    app.mount('/static', StaticFiles(directory=str(settings.template_dir.parent / 'static')), name='static')

    @app.get('/healthz')
    def healthz(db: Session = Depends(get_db)):
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        return {'ok': True, 'service': settings.app_name, 'users': user_count}

    @app.get('/', response_class=HTMLResponse)
    def index(request: Request, db: Session = Depends(get_db)):
        session_user = maybe_get_current_user(request, db)
        context = {
            'request': request,
            'app_name': settings.app_name,
            'database_url': settings.database_url,
            'user_count': db.scalar(select(func.count()).select_from(User)) or 0,
        }
        context.update(_build_home_context(settings, db, request))
        if session_user is not None:
            context.setdefault('session_ui', {})
            context['session_ui']['current_user'] = {
                'username': session_user.username,
                'role': session_user.role,
            }
        return templates.TemplateResponse('index-kawaii.html', context)
    
    @app.get('/v2')
    def index_v2_redirect():
        return RedirectResponse(url='/', status_code=307)

    @app.get('/skills', response_class=HTMLResponse)
    def skills_page(
        request: Request,
        limit: int = Query(default=12, ge=1, le=50),
        db: Session = Depends(get_db),
    ):
        actor = _require_lifecycle_actor(request, db, 'maintainer', 'contributor')
        if isinstance(actor, RedirectResponse):
            return actor
        if isinstance(actor, dict):
            return templates.TemplateResponse('console-forbidden.html', actor, status_code=403)

        lang = _resolve_language(request)
        user = actor.user
        principal_id = actor.principal.id if actor.principal else None
        scope = _load_registry_scope(
            db,
            principal_id=principal_id,
            include_all=user.role == 'maintainer',
        )
        skills = scope['skills']
        drafts = scope['drafts']
        versions = scope['versions']
        releases = scope['releases']
        exposures = scope['exposures']
        review_cases = scope['review_cases']
        principals_by_id = _first_by_id(scope['principals'])
        drafts_by_skill = _group_by(drafts, 'skill_id')
        versions_by_skill = _group_by(versions, 'skill_id')
        releases_by_version = _group_by(releases, 'skill_version_id')
        exposures_by_release = _group_by(exposures, 'release_id')
        review_cases_by_exposure = _group_by(review_cases, 'exposure_id')
        versions_by_id = _first_by_id(versions)
        skills_by_id = _first_by_id(skills)

        skill_items = []
        for skill in skills[:limit]:
            skill_versions = versions_by_skill.get(skill.id, [])
            skill_releases = []
            for version in skill_versions:
                skill_releases.extend(releases_by_version.get(version.id, []))
            skill_items.append(
                {
                    'id': skill.id,
                    'display_name': skill.display_name,
                    'slug': skill.slug,
                    'summary': skill.summary or _pick_lang(lang, '尚未填写技能摘要。', 'No skill summary yet.'),
                    'namespace': _principal_label(principals_by_id.get(skill.namespace_id)),
                    'default_visibility_profile': skill.default_visibility_profile or '-',
                    'draft_count': len(drafts_by_skill.get(skill.id, [])),
                    'version_count': len(skill_versions),
                    'release_count': len(skill_releases),
                    'updated_at': _humanize_timestamp(skill.updated_at.isoformat()),
                    'detail_href': _with_lang(f'/skills/{skill.id}', lang),
                }
            )

        draft_items = []
        for draft in drafts[:limit]:
            skill = skills_by_id.get(draft.skill_id)
            metadata = _load_json_object(draft.metadata_json)
            draft_items.append(
                {
                    'id': draft.id,
                    'skill_name': skill.display_name if skill else f'Skill #{draft.skill_id}',
                    'state': _humanize_status(draft.state, lang),
                    'content_ref': draft.content_ref or '-',
                    'entrypoint': metadata.get('entrypoint') or '-',
                    'updated_at': _humanize_timestamp(draft.updated_at.isoformat()),
                    'detail_href': _with_lang(f'/drafts/{draft.id}', lang),
                }
            )

        release_items = []
        for release in releases[:limit]:
            version = versions_by_id.get(release.skill_version_id)
            skill = skills_by_id.get(version.skill_id) if version else None
            release_items.append(
                {
                    'id': release.id,
                    'skill_name': skill.display_name if skill else f'Skill #{version.skill_id if version else "?"}',
                    'version': version.version if version else '-',
                    'state': _humanize_status(release.state, lang),
                    'ready_at': _humanize_timestamp(release.ready_at),
                    'exposure_count': len(exposures_by_release.get(release.id, [])),
                    'detail_href': _with_lang(f'/releases/{release.id}', lang),
                    'share_href': _with_lang(f'/releases/{release.id}/share', lang),
                }
            )

        share_items = []
        for exposure in exposures[:limit]:
            release = next((item for item in releases if item.id == exposure.release_id), None)
            version = versions_by_id.get(release.skill_version_id) if release else None
            skill = skills_by_id.get(version.skill_id) if version else None
            review_case = (review_cases_by_exposure.get(exposure.id) or [None])[0]
            share_items.append(
                {
                    'id': exposure.id,
                    'skill_name': skill.display_name if skill else '-',
                    'release_id': exposure.release_id,
                    'audience': _humanize_audience_type(exposure.audience_type, lang),
                    'listing_mode': _humanize_listing_mode(exposure.listing_mode, lang),
                    'install_mode': _humanize_install_mode(exposure.install_mode, lang),
                    'review_gate': _humanize_review_gate(exposure.review_requirement, lang),
                    'state': _humanize_status(exposure.state, lang),
                    'review_case_state': _humanize_review_gate(review_case.state if review_case else 'none', lang),
                    'share_href': _with_lang(f'/releases/{exposure.release_id}/share', lang),
                }
            )

        review_items = []
        for review_case in review_cases[:limit]:
            exposure = next((item for item in exposures if item.id == review_case.exposure_id), None)
            release = next((item for item in releases if item.id == exposure.release_id), None) if exposure else None
            version = versions_by_id.get(release.skill_version_id) if release else None
            skill = skills_by_id.get(version.skill_id) if version else None
            review_items.append(
                {
                    'id': review_case.id,
                    'skill_name': skill.display_name if skill else '-',
                    'audience': _humanize_audience_type(exposure.audience_type if exposure else None, lang),
                    'mode': _humanize_review_gate(review_case.mode, lang),
                    'state': _humanize_review_gate(review_case.state, lang),
                    'opened_at': _humanize_timestamp(review_case.opened_at.isoformat()),
                    'review_href': _with_lang('/review-cases', lang),
                }
            )

        total_credentials = int(len(scope['credentials']))
        total_grants = int(len(scope['grants']))
        context = _build_lifecycle_console_context(
            request=request,
            title=_pick_lang(lang, '技能生命周期', 'Skill lifecycle'),
            content=_pick_lang(
                lang,
                '用新的领域语言查看技能、草稿、发布、分享和审核状态，所有流转都收拢到同一套 private-first 生命周期里。',
                'Track skills, drafts, releases, sharing, and review with one private-first lifecycle vocabulary.',
            ),
            limit=limit,
            items=skill_items,
            cli_command='python scripts/registryctl.py --base-url https://skills.example.com --token <token> skills get <skill-id>',
            stats=[
                {'value': str(len(skills)), 'label': _pick_lang(lang, '技能', 'Skills'), 'detail': _pick_lang(lang, '当前可见技能', 'Visible skills')},
                {'value': str(len(drafts)), 'label': _pick_lang(lang, '草稿', 'Drafts'), 'detail': _pick_lang(lang, '可继续编辑', 'Still editable')},
                {'value': str(len(releases)), 'label': _pick_lang(lang, '发布', 'Releases'), 'detail': _pick_lang(lang, '已生成 release', 'Materialized releases')},
                {'value': str(len(exposures)), 'label': _pick_lang(lang, '分享', 'Share'), 'detail': _pick_lang(lang, '暴露策略', 'Exposure policies')},
                {'value': str(total_credentials + total_grants), 'label': _pick_lang(lang, '访问', 'Access'), 'detail': _pick_lang(lang, '令牌与授权', 'Tokens and grants')},
                {'value': str(len(review_cases)), 'label': _pick_lang(lang, '审核', 'Review'), 'detail': _pick_lang(lang, '公开流转审核单', 'Review cases for exposure')},
            ],
        )
        context.update(
            {
                'skill_items': skill_items,
                'draft_items': draft_items,
                'release_items': release_items,
                'share_items': share_items,
                'review_items': review_items,
                'access_href': _with_lang('/access/tokens', lang),
                'review_cases_href': _with_lang('/review-cases', lang),
            }
        )
        return templates.TemplateResponse('skills.html', context)

    @app.get('/skills/{skill_id}', response_class=HTMLResponse)
    def skill_detail_page(
        skill_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = _require_lifecycle_actor(request, db, 'maintainer', 'contributor')
        if isinstance(actor, RedirectResponse):
            return actor
        if isinstance(actor, dict):
            return templates.TemplateResponse('console-forbidden.html', actor, status_code=403)

        skill = db.get(Skill, skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail='skill not found')
        if not _is_owner(actor.user, actor.principal.id if actor.principal else None, skill.namespace_id):
            return templates.TemplateResponse(
                'console-forbidden.html',
                _build_console_forbidden_context(request, actor.user, 'maintainer', 'contributor'),
                status_code=403,
            )

        lang = _resolve_language(request)
        drafts = db.scalars(
            select(SkillDraft)
            .where(SkillDraft.skill_id == skill.id)
            .order_by(SkillDraft.updated_at.desc(), SkillDraft.id.desc())
        ).all()
        versions = db.scalars(
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill.id)
            .order_by(SkillVersion.created_at.desc(), SkillVersion.id.desc())
        ).all()
        version_ids = [version.id for version in versions]
        releases = []
        if version_ids:
            releases = db.scalars(
                select(Release)
                .where(Release.skill_version_id.in_(version_ids))
                .order_by(Release.created_at.desc(), Release.id.desc())
            ).all()
        versions_by_id = _first_by_id(versions)
        principal = db.get(Principal, skill.namespace_id)

        draft_rows = [
            {
                'id': draft.id,
                'state': _humanize_status(draft.state, lang),
                'content_ref': draft.content_ref or '-',
                'updated_at': _humanize_timestamp(draft.updated_at.isoformat()),
                'detail_href': _with_lang(f'/drafts/{draft.id}', lang),
            }
            for draft in drafts
        ]
        version_rows = [
            {
                'id': version.id,
                'version': version.version,
                'created_at': _humanize_timestamp(version.created_at.isoformat()),
                'release_href': _with_lang(
                    f"/releases/{next((release.id for release in releases if release.skill_version_id == version.id), 0)}",
                    lang,
                ) if any(release.skill_version_id == version.id for release in releases) else '',
            }
            for version in versions
        ]
        release_rows = [
            {
                'id': release.id,
                'version': versions_by_id.get(release.skill_version_id).version if versions_by_id.get(release.skill_version_id) else '-',
                'state': _humanize_status(release.state, lang),
                'ready_at': _humanize_timestamp(release.ready_at),
                'detail_href': _with_lang(f'/releases/{release.id}', lang),
                'share_href': _with_lang(f'/releases/{release.id}/share', lang),
            }
            for release in releases
        ]
        context = _build_lifecycle_console_context(
            request=request,
            title=skill.display_name,
            content=_pick_lang(
                lang,
                '这是技能命名空间下的单个技能视图，可直接追踪草稿、版本和发布状态。',
                'This skill detail view tracks drafts, versions, and releases inside one namespace.',
            ),
            limit=max(len(drafts), len(releases), 1),
            items=release_rows,
            cli_command=f'python scripts/registryctl.py --base-url https://skills.example.com --token <token> skills get {skill.id}',
            stats=[
                {'value': _principal_label(principal), 'label': _pick_lang(lang, '命名空间', 'Namespace'), 'detail': skill.slug},
                {'value': str(len(drafts)), 'label': _pick_lang(lang, '草稿', 'Drafts'), 'detail': _pick_lang(lang, '当前技能草稿', 'Open drafts')},
                {'value': str(len(releases)), 'label': _pick_lang(lang, '发布', 'Releases'), 'detail': _pick_lang(lang, '关联 release', 'Linked releases')},
            ],
        )
        context.update(
            {
                'skill': {
                    'id': skill.id,
                    'display_name': skill.display_name,
                    'slug': skill.slug,
                    'summary': skill.summary or _pick_lang(lang, '尚未填写摘要。', 'No summary yet.'),
                    'namespace': _principal_label(principal),
                    'default_visibility_profile': skill.default_visibility_profile or '-',
                    'status': _humanize_status(skill.status, lang),
                    'updated_at': _humanize_timestamp(skill.updated_at.isoformat()),
                },
                'draft_rows': draft_rows,
                'version_rows': version_rows,
                'release_rows': release_rows,
            }
        )
        return templates.TemplateResponse('skill-detail.html', context)

    @app.get('/drafts/{draft_id}', response_class=HTMLResponse)
    def draft_detail_page(
        draft_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = _require_lifecycle_actor(request, db, 'maintainer', 'contributor')
        if isinstance(actor, RedirectResponse):
            return actor
        if isinstance(actor, dict):
            return templates.TemplateResponse('console-forbidden.html', actor, status_code=403)

        draft = db.get(SkillDraft, draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail='draft not found')
        skill = db.get(Skill, draft.skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail='skill not found')
        if not _is_owner(actor.user, actor.principal.id if actor.principal else None, skill.namespace_id):
            return templates.TemplateResponse(
                'console-forbidden.html',
                _build_console_forbidden_context(request, actor.user, 'maintainer', 'contributor'),
                status_code=403,
            )

        lang = _resolve_language(request)
        base_version = db.get(SkillVersion, draft.base_version_id) if draft.base_version_id else None
        metadata = _load_json_object(draft.metadata_json)
        context = _build_lifecycle_console_context(
            request=request,
            title=_pick_lang(lang, '草稿详情', 'Draft detail'),
            content=_pick_lang(
                lang,
                '草稿是可编辑工作区。这里展示内容引用、元数据快照以及后续封版关系。',
                'Drafts are editable workspaces. This view shows content refs, metadata snapshots, and the later sealed lineage.',
            ),
            limit=1,
            items=[],
            cli_command=f'python scripts/registryctl.py --base-url https://skills.example.com --token <token> drafts update {draft.id} --metadata-json \'{{}}\'',
            stats=[
                {'value': _humanize_status(draft.state, lang), 'label': _pick_lang(lang, '状态', 'State'), 'detail': _pick_lang(lang, '草稿当前状态', 'Current draft state')},
                {'value': base_version.version if base_version else '-', 'label': _pick_lang(lang, '基线版本', 'Base version'), 'detail': _pick_lang(lang, '可为空', 'Optional')},
                {'value': _humanize_timestamp(draft.updated_at.isoformat()), 'label': _pick_lang(lang, '更新时间', 'Updated'), 'detail': skill.display_name},
            ],
        )
        context.update(
            {
                'draft': {
                    'id': draft.id,
                    'skill_name': skill.display_name,
                    'state': _humanize_status(draft.state, lang),
                    'content_ref': draft.content_ref or '-',
                    'base_version': base_version.version if base_version else '-',
                    'updated_at': _humanize_timestamp(draft.updated_at.isoformat()),
                    'metadata_pretty': json.dumps(metadata, ensure_ascii=False, indent=2) if metadata else '{}',
                    'skill_href': _with_lang(f'/skills/{skill.id}', lang),
                }
            }
        )
        return templates.TemplateResponse('draft-detail.html', context)

    @app.get('/releases/{release_id}', response_class=HTMLResponse)
    def release_detail_page(
        release_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = _require_lifecycle_actor(request, db, 'maintainer', 'contributor')
        if isinstance(actor, RedirectResponse):
            return actor
        if isinstance(actor, dict):
            return templates.TemplateResponse('console-forbidden.html', actor, status_code=403)

        release = db.get(Release, release_id)
        if release is None:
            raise HTTPException(status_code=404, detail='release not found')
        version = db.get(SkillVersion, release.skill_version_id)
        if version is None:
            raise HTTPException(status_code=404, detail='skill version not found')
        skill = db.get(Skill, version.skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail='skill not found')
        if not _is_owner(actor.user, actor.principal.id if actor.principal else None, skill.namespace_id):
            return templates.TemplateResponse(
                'console-forbidden.html',
                _build_console_forbidden_context(request, actor.user, 'maintainer', 'contributor'),
                status_code=403,
            )

        lang = _resolve_language(request)
        artifacts = db.scalars(
            select(Artifact)
            .where(Artifact.release_id == release.id)
            .order_by(Artifact.kind.asc(), Artifact.id.asc())
        ).all()
        exposures = db.scalars(
            select(Exposure)
            .where(Exposure.release_id == release.id)
            .order_by(Exposure.id.desc())
        ).all()
        artifact_rows = [
            {
                'id': artifact.id,
                'kind': _humanize_identifier(artifact.kind),
                'sha256': artifact.sha256 or '-',
                'size_bytes': str(artifact.size_bytes),
                'storage_uri': artifact.storage_uri or '-',
            }
            for artifact in artifacts
        ]
        exposure_rows = [
            {
                'id': exposure.id,
                'audience': _humanize_audience_type(exposure.audience_type, lang),
                'state': _humanize_status(exposure.state, lang),
                'listing_mode': _humanize_listing_mode(exposure.listing_mode, lang),
                'share_href': _with_lang(f'/releases/{release.id}/share', lang),
            }
            for exposure in exposures
        ]
        context = _build_lifecycle_console_context(
            request=request,
            title=_pick_lang(lang, '发布详情', 'Release detail'),
            content=_pick_lang(
                lang,
                '发布是不可变交付物。这里把产物、可见性和后续分享策略集中在一起。',
                'A release is the immutable delivery unit. This page groups artifacts, visibility, and downstream sharing state together.',
            ),
            limit=max(len(artifacts), len(exposures), 1),
            items=artifact_rows,
            cli_command=f'python scripts/registryctl.py --base-url https://skills.example.com --token <token> releases get {release.id}',
            stats=[
                {'value': skill.display_name, 'label': _pick_lang(lang, '技能', 'Skill'), 'detail': version.version},
                {'value': _humanize_status(release.state, lang), 'label': _pick_lang(lang, '状态', 'State'), 'detail': _pick_lang(lang, 'release 生命周期', 'Release lifecycle')},
                {'value': str(len(artifacts)), 'label': _pick_lang(lang, '产物', 'Artifacts'), 'detail': _pick_lang(lang, 'manifest / bundle / signature', 'manifest / bundle / signature')},
                {'value': str(len(exposures)), 'label': _pick_lang(lang, '分享', 'Share'), 'detail': _pick_lang(lang, '可见性出口', 'Audience exits')},
            ],
        )
        context.update(
            {
                'release': {
                    'id': release.id,
                    'skill_name': skill.display_name,
                    'version': version.version,
                    'state': _humanize_status(release.state, lang),
                    'format_version': release.format_version,
                    'ready_at': _humanize_timestamp(release.ready_at),
                    'created_at': _humanize_timestamp(release.created_at.isoformat()),
                    'skill_href': _with_lang(f'/skills/{skill.id}', lang),
                    'share_href': _with_lang(f'/releases/{release.id}/share', lang),
                },
                'artifact_rows': artifact_rows,
                'exposure_rows': exposure_rows,
            }
        )
        return templates.TemplateResponse('release-detail.html', context)

    @app.get('/releases/{release_id}/share', response_class=HTMLResponse)
    def release_share_page(
        release_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = _require_lifecycle_actor(request, db, 'maintainer', 'contributor')
        if isinstance(actor, RedirectResponse):
            return actor
        if isinstance(actor, dict):
            return templates.TemplateResponse('console-forbidden.html', actor, status_code=403)

        release = db.get(Release, release_id)
        if release is None:
            raise HTTPException(status_code=404, detail='release not found')
        version = db.get(SkillVersion, release.skill_version_id)
        if version is None:
            raise HTTPException(status_code=404, detail='skill version not found')
        skill = db.get(Skill, version.skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail='skill not found')
        if not _is_owner(actor.user, actor.principal.id if actor.principal else None, skill.namespace_id):
            return templates.TemplateResponse(
                'console-forbidden.html',
                _build_console_forbidden_context(request, actor.user, 'maintainer', 'contributor'),
                status_code=403,
            )

        lang = _resolve_language(request)
        exposures = db.scalars(
            select(Exposure)
            .where(Exposure.release_id == release.id)
            .order_by(Exposure.id.asc())
        ).all()
        exposure_ids = [exposure.id for exposure in exposures]
        review_cases = []
        grants = []
        if exposure_ids:
            review_cases = db.scalars(
                select(ReviewCase)
                .where(ReviewCase.exposure_id.in_(exposure_ids))
                .order_by(ReviewCase.id.desc())
            ).all()
            grants = db.scalars(
                select(AccessGrant)
                .where(AccessGrant.exposure_id.in_(exposure_ids))
                .order_by(AccessGrant.id.desc())
            ).all()
        review_cases_by_exposure = _group_by(review_cases, 'exposure_id')
        grants_by_exposure = _group_by(grants, 'exposure_id')
        share_rows = []
        for exposure in exposures:
            review_case = (review_cases_by_exposure.get(exposure.id) or [None])[0]
            share_rows.append(
                {
                    'id': exposure.id,
                    'audience': _humanize_audience_type(exposure.audience_type, lang),
                    'listing_mode': _humanize_listing_mode(exposure.listing_mode, lang),
                    'install_mode': _humanize_install_mode(exposure.install_mode, lang),
                    'review_requirement': _humanize_review_gate(exposure.review_requirement, lang),
                    'review_case_state': _humanize_review_gate(review_case.state if review_case else 'none', lang),
                    'grant_count': len(grants_by_exposure.get(exposure.id, [])),
                    'state': _humanize_status(exposure.state, lang),
                }
            )
        context = _build_lifecycle_console_context(
            request=request,
            title=_pick_lang(lang, '分享与可见性', 'Share and visibility'),
            content=_pick_lang(
                lang,
                '一个 release 可以同时拥有私人、令牌共享和公开三种出口。公开出口必须经过审核，私人出口可直接启用。',
                'A release can expose private, token-shared, and public audiences at the same time. Public audiences must pass review while private ones can activate directly.',
            ),
            limit=max(len(share_rows), 1),
            items=share_rows,
            cli_command=f'python scripts/registryctl.py --base-url https://skills.example.com --token <token> exposures create {release.id} --audience-type public',
            stats=[
                {'value': skill.display_name, 'label': _pick_lang(lang, '技能', 'Skill'), 'detail': version.version},
                {'value': str(sum(1 for item in exposures if item.audience_type == "private")), 'label': _pick_lang(lang, '私人', 'Private'), 'detail': _pick_lang(lang, '仅作者侧', 'Author-side only')},
                {'value': str(sum(1 for item in exposures if item.audience_type == "grant")), 'label': _pick_lang(lang, '令牌共享', 'Shared by token'), 'detail': _pick_lang(lang, '细到 token', 'Token-scoped access')},
                {'value': str(sum(1 for item in exposures if item.audience_type == "public")), 'label': _pick_lang(lang, '公开', 'Public'), 'detail': _pick_lang(lang, '匿名可见', 'Anonymous install path')},
            ],
        )
        context.update(
            {
                'release': {
                    'id': release.id,
                    'skill_name': skill.display_name,
                    'version': version.version,
                    'detail_href': _with_lang(f'/releases/{release.id}', lang),
                },
                'share_rows': share_rows,
            }
        )
        return templates.TemplateResponse('share-detail.html', context)

    @app.get('/access/tokens', response_class=HTMLResponse)
    def access_tokens_page(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        db: Session = Depends(get_db),
    ):
        actor = _require_lifecycle_actor(request, db, 'maintainer', 'contributor')
        if isinstance(actor, RedirectResponse):
            return actor
        if isinstance(actor, dict):
            return templates.TemplateResponse('console-forbidden.html', actor, status_code=403)

        lang = _resolve_language(request)
        user = actor.user
        principal_id = actor.principal.id if actor.principal else None
        scope = _load_registry_scope(
            db,
            principal_id=principal_id,
            include_all=user.role == 'maintainer',
        )
        principals_by_id = _first_by_id(scope['principals'])
        grants_by_id = _first_by_id(scope['grants'])
        exposures_by_id = _first_by_id(scope['exposures'])
        releases_by_id = _first_by_id(scope['releases'])
        versions_by_id = _first_by_id(scope['versions'])
        skills_by_id = _first_by_id(scope['skills'])

        credential_rows = []
        for credential in scope['credentials'][:limit]:
            grant = grants_by_id.get(credential.grant_id) if credential.grant_id else None
            exposure = exposures_by_id.get(grant.exposure_id) if grant else None
            release = releases_by_id.get(exposure.release_id) if exposure else None
            version = versions_by_id.get(release.skill_version_id) if release else None
            skill = skills_by_id.get(version.skill_id) if version else None
            credential_rows.append(
                {
                    'id': credential.id,
                    'type': _humanize_identifier(credential.type),
                    'principal': _principal_label(principals_by_id.get(credential.principal_id)),
                    'scopes': ', '.join(_load_json_list(credential.scopes_json)) or '-',
                    'grant_id': grant.id if grant else '-',
                    'release_label': f'{skill.display_name} {version.version}' if skill and version else '-',
                    'expires_at': _humanize_timestamp(credential.expires_at),
                    'last_used_at': _humanize_timestamp(credential.last_used_at),
                }
            )

        grant_rows = []
        for grant in scope['grants'][:limit]:
            exposure = exposures_by_id.get(grant.exposure_id)
            release = releases_by_id.get(exposure.release_id) if exposure else None
            version = versions_by_id.get(release.skill_version_id) if release else None
            skill = skills_by_id.get(version.skill_id) if version else None
            grant_rows.append(
                {
                    'id': grant.id,
                    'grant_type': _humanize_identifier(grant.grant_type),
                    'subject_ref': grant.subject_ref or '-',
                    'state': _humanize_status(grant.state, lang),
                    'audience': _humanize_audience_type(exposure.audience_type if exposure else None, lang),
                    'release_label': f'{skill.display_name} {version.version}' if skill and version else '-',
                }
            )

        context = _build_lifecycle_console_context(
            request=request,
            title=_pick_lang(lang, '访问令牌与授权', 'Access tokens and grants'),
            content=_pick_lang(
                lang,
                '这里同时展示个人 token 和 grant 绑定令牌。后续要做更细粒度权限，只需要在 grant / credential 层扩展，不必再改技能生命周期。',
                'This page groups personal tokens and grant-bound credentials. Finer permission models can grow inside grants and credentials without reshaping the skill lifecycle.',
            ),
            limit=limit,
            items=credential_rows,
            cli_command='python scripts/registryctl.py --base-url https://skills.example.com --token <token> tokens me',
            stats=[
                {'value': str(len(scope['credentials'])), 'label': _pick_lang(lang, '令牌', 'Tokens'), 'detail': _pick_lang(lang, '当前可见 credential', 'Visible credentials')},
                {'value': str(sum(1 for item in scope["credentials"] if item.type == "personal_token")), 'label': _pick_lang(lang, '个人', 'Personal'), 'detail': _pick_lang(lang, '用户会话 token', 'User session tokens')},
                {'value': str(sum(1 for item in scope["credentials"] if item.type == "grant_token")), 'label': _pick_lang(lang, '授权', 'Grant'), 'detail': _pick_lang(lang, '共享 / 安装 token', 'Shared install tokens')},
                {'value': str(len(scope['grants'])), 'label': _pick_lang(lang, '授权记录', 'Grant records'), 'detail': _pick_lang(lang, '与 exposure 绑定', 'Bound to exposures')},
            ],
        )
        context.update({'credential_rows': credential_rows, 'grant_rows': grant_rows})
        return templates.TemplateResponse('access-tokens.html', context)

    @app.get('/review-cases', response_class=HTMLResponse)
    def review_cases_page(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        db: Session = Depends(get_db),
    ):
        actor = _require_lifecycle_actor(request, db, 'maintainer', 'contributor')
        if isinstance(actor, RedirectResponse):
            return actor
        if isinstance(actor, dict):
            return templates.TemplateResponse('console-forbidden.html', actor, status_code=403)

        lang = _resolve_language(request)
        user = actor.user
        principal_id = actor.principal.id if actor.principal else None
        scope = _load_registry_scope(
            db,
            principal_id=principal_id,
            include_all=user.role == 'maintainer',
        )
        exposures_by_id = _first_by_id(scope['exposures'])
        releases_by_id = _first_by_id(scope['releases'])
        versions_by_id = _first_by_id(scope['versions'])
        skills_by_id = _first_by_id(scope['skills'])

        review_rows = []
        for review_case in scope['review_cases'][:limit]:
            exposure = exposures_by_id.get(review_case.exposure_id)
            release = releases_by_id.get(exposure.release_id) if exposure else None
            version = versions_by_id.get(release.skill_version_id) if release else None
            skill = skills_by_id.get(version.skill_id) if version else None
            review_rows.append(
                {
                    'id': review_case.id,
                    'skill_name': skill.display_name if skill else '-',
                    'audience': _humanize_audience_type(exposure.audience_type if exposure else None, lang),
                    'mode': _humanize_review_gate(review_case.mode, lang),
                    'state': _humanize_review_gate(review_case.state, lang),
                    'opened_at': _humanize_timestamp(review_case.opened_at.isoformat()),
                    'closed_at': _humanize_timestamp(review_case.closed_at),
                }
            )
        context = _build_lifecycle_console_context(
            request=request,
            title=_pick_lang(lang, '审核收件箱', 'Review inbox'),
            content=_pick_lang(
                lang,
                '公开技能必须经过审核。这个收件箱把公开 exposure 的审核需求和当前结论统一放在一起。',
                'Public skills must pass review. This inbox gathers review needs and current outcomes for public-facing exposures.',
            ),
            limit=limit,
            items=review_rows,
            cli_command='python scripts/registryctl.py --base-url https://skills.example.com --token <token> reviews get-case <review-case-id>',
            stats=[
                {'value': str(len(scope['review_cases'])), 'label': _pick_lang(lang, '总数', 'Total'), 'detail': _pick_lang(lang, '当前可见 case', 'Visible review cases')},
                {'value': str(sum(1 for item in scope["review_cases"] if item.state == "open")), 'label': _pick_lang(lang, '待处理', 'Open'), 'detail': _pick_lang(lang, '仍待结论', 'Still awaiting a decision')},
                {'value': str(sum(1 for item in scope["review_cases"] if item.state == "approved")), 'label': _pick_lang(lang, '已通过', 'Approved'), 'detail': _pick_lang(lang, '可以公开', 'Ready for public install')},
                {'value': str(sum(1 for item in scope["review_cases"] if item.state == "rejected")), 'label': _pick_lang(lang, '已拒绝', 'Rejected'), 'detail': _pick_lang(lang, '需要回退策略', 'Needs a fallback audience')},
            ],
        )
        context.update({'review_rows': review_rows})
        return templates.TemplateResponse('review-cases.html', context)

    @app.get('/login', response_class=HTMLResponse)
    def login(request: Request):
        lang = _resolve_language(request)
        page_eyebrow = _pick_lang(lang, '维护控制台', 'Maintainer-only console')
        page_kicker = _pick_lang(lang, '认证入口', 'Auth entry')
        content = _pick_lang(
            lang,
            '使用由托管控制台签发的 Bearer Token 调用 API 路由。',
            'Use a bearer token created by the hosted control plane to access API routes.',
        )
        return templates.TemplateResponse(
            'login-kawaii.html',
            {
                'request': request,
                'title': _pick_lang(lang, '登录', 'Login'),
                'content': content,
                'page_eyebrow': page_eyebrow,
                'page_kicker': page_kicker,
                'page_mode': 'console',
                'show_console_session': False,
                'nav_links': _site_nav(home=False, lang=lang),
                'cli_command': 'curl -H "Authorization: Bearer <token>" https://skills.example.com/api/v1/me',
                'page_stats': [
                    {
                        'value': _pick_lang(lang, 'Bearer Token', 'Bearer Token'),
                        'label': _pick_lang(lang, '认证方式', 'Auth scheme'),
                        'detail': _pick_lang(lang, '由控制台签发', 'Issued by control plane'),
                    },
                    {
                        'value': '/api/v1/me',
                        'label': _pick_lang(lang, '首个检查点', 'First probe'),
                        'detail': _pick_lang(lang, '验证 token 是否生效', 'Validate token works'),
                    },
                    {
                        'value': '/skills',
                        'label': _pick_lang(lang, '维护入口', 'Maintainer entry'),
                        'detail': _pick_lang(lang, '进入技能生命周期控制台', 'Enter the skill lifecycle console'),
                    },
                ],
                **_build_kawaii_ui_context(request, lang, page_kicker, page_eyebrow),
            },
        )

    @app.get('/api/v1/me')
    def read_me(user: User = Depends(get_current_user)):
        return {
            'id': user.id,
            'username': user.username,
            'display_name': user.display_name,
            'role': user.role,
        }

    app.include_router(auth_router)
    app.include_router(background_router)
    app.include_router(search_router)
    app.include_router(access_router)
    app.include_router(authoring_router)
    app.include_router(discovery_router)
    app.include_router(release_router)
    app.include_router(exposure_router)
    app.include_router(review_router)
    app.include_router(registry_router)

    return app


app = create_app()
