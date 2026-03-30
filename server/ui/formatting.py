from __future__ import annotations

import json
from datetime import datetime

from fastapi import Request

from server.auth import AUTH_COOKIE_NAME
from server.ui.i18n import build_language_switches, pick_lang, with_lang


def load_json_object(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


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
        return pick_lang(lang, "暂无快照", "No snapshot")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return value


def humanize_identifier(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("_", " ").replace("-", " ").strip().title()


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
    return _humanize_with_mapping(
        status,
        lang,
        {
            "draft": ("草稿", "Draft"),
            "open": ("打开", "Open"),
            "sealed": ("已封版", "Sealed"),
            "ready": ("已就绪", "Ready"),
            "active": ("已生效", "Active"),
            "revoked": ("已撤销", "Revoked"),
            "pending_policy": ("等待策略", "Pending policy"),
            "review_open": ("审核进行中", "Review open"),
            "validation_requested": ("等待校验", "Waiting validation"),
            "review_requested": ("待评审", "Waiting review"),
            "approved": ("已批准", "Approved"),
            "rejected": ("已驳回", "Rejected"),
            "validated": ("已校验", "Validated"),
            "promoted": ("已提升", "Promoted"),
            "published": ("已发布", "Published"),
            "pending": ("待处理", "Pending"),
            "queued": ("排队中", "Queued"),
            "running": ("运行中", "Running"),
            "completed": ("已完成", "Completed"),
            "failed": ("失败", "Failed"),
        },
    )


def humanize_job_kind(kind: str | None, lang: str) -> str:
    return _humanize_with_mapping(
        kind,
        lang,
        {"materialize_release": ("生成发布产物", "Materialize release")},
    )


def humanize_role(role: str | None, lang: str) -> str:
    return _humanize_with_mapping(
        role,
        lang,
        {
            "maintainer": ("维护者", "Maintainer"),
            "contributor": ("贡献者", "Contributor"),
        },
    )


def humanize_audience_type(audience_type: str | None, lang: str) -> str:
    return _humanize_with_mapping(
        audience_type,
        lang,
        {
            "private": ("私人", "Private"),
            "grant": ("令牌共享", "Shared by token"),
            "public": ("公开", "Public"),
        },
    )


def humanize_listing_mode(listing_mode: str | None, lang: str) -> str:
    return _humanize_with_mapping(
        listing_mode,
        lang,
        {
            "listed": ("可列出", "Listed"),
            "direct_only": ("仅直达", "Direct only"),
        },
    )


def humanize_install_mode(install_mode: str | None, lang: str) -> str:
    return _humanize_with_mapping(
        install_mode,
        lang,
        {
            "enabled": ("允许安装", "Install enabled"),
            "disabled": ("禁止安装", "Install disabled"),
        },
    )


def humanize_review_gate(review_gate: str | None, lang: str) -> str:
    return _humanize_with_mapping(
        review_gate,
        lang,
        {
            "none": ("无需审核", "No review"),
            "advisory": ("建议审核", "Advisory review"),
            "blocking": ("阻塞审核", "Blocking review"),
            "open": ("待审核", "Open"),
            "approved": ("已通过", "Approved"),
            "rejected": ("已拒绝", "Rejected"),
        },
    )


def humanize_timestamp(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return value
    stamp = parsed.strftime("%Y-%m-%d %H:%M")
    if parsed.tzinfo is not None and parsed.utcoffset() is not None:
        stamp = f"{stamp} UTC"
    return stamp


def build_kawaii_ui_context(
    request: Request,
    lang: str,
    page_kicker: str,
    page_eyebrow: str,
) -> dict:
    return {
        "page_language": lang,
        "page_lang_attr": "zh-CN" if lang == "zh" else "en",
        "home_href": with_lang("/", lang),
        "session_ui": {
            "has_auth_cookie_hint": bool(request.cookies.get(AUTH_COOKIE_NAME)),
        },
        "language_switches": build_language_switches(request, lang),
        "theme_switches": [
            {"value": "light", "label": pick_lang(lang, "浅色", "Light")},
            {"value": "dark", "label": pick_lang(lang, "深色", "Dark")},
        ],
        "ui": {
            "brand_subtitle": pick_lang(lang, "私人技能库", "Private skill library"),
            "theme_toggle_label": pick_lang(lang, "主题切换", "Theme switcher"),
            "language_toggle_label": pick_lang(lang, "语言切换", "Language switcher"),
            "copy_success": pick_lang(lang, "已复制", "Copied"),
            "copy_error": pick_lang(lang, "复制失败", "Copy failed"),
            "toast_close": pick_lang(lang, "关闭提示", "Dismiss notification"),
            "copy_icon_title": pick_lang(lang, "复制", "Copy"),
            "copy_button_label": pick_lang(lang, "复制", "Copy"),
            "status_running": pick_lang(lang, "运行中", "Running"),
            "search_placeholder": pick_lang(lang, "搜索技能或命令", "Search skills or commands"),
            "search_results_label": pick_lang(lang, "搜索结果", "Search results"),
            "search_skills_label": pick_lang(lang, "技能", "Skills"),
            "search_commands_label": pick_lang(lang, "命令", "Commands"),
            "search_empty_label": pick_lang(lang, "未找到匹配结果", "No matching results"),
            "search_create_label": pick_lang(lang, "创建新技能", "Create skill"),
            "search_create_command": "scripts/new-skill.sh lvxiaoer/my-skill basic",
            "search_auth_required": pick_lang(
                lang,
                "请先登录后搜索私人技能库",
                "Sign in to search the private-first library",
            ),
            "page_kicker": page_kicker,
            "page_eyebrow": page_eyebrow,
            "handoff_title": pick_lang(lang, "交接台", "Hand-off desk"),
            "handoff_human_tab": pick_lang(lang, "交任务", "Delegate"),
            "handoff_agent_tab": pick_lang(lang, "执行命令", "Run command"),
            "copy_prompt_action": pick_lang(lang, "复制这条提示", "Copy this prompt"),
            "cli_mirror_label": pick_lang(lang, "命令镜像", "CLI mirror"),
            "console_section_title": pick_lang(lang, "有事再进维护台", "Open console when needed"),
            "skills_section_title": pick_lang(lang, "常用技能", "Popular skills"),
            "skills_section_subtitle": pick_lang(
                lang,
                "从目录里挑 3 个入口，先检查再交给 Agent。",
                "Pick 3 likely entries, inspect first, then hand them off.",
            ),
            "featured_skill_fallback": pick_lang(lang, "精选", "Featured"),
            "copy_inspect_action": pick_lang(lang, "复制检查命令", "Copy inspect command"),
            "go_handoff_action": pick_lang(lang, "去交接台", "Go to hand-off"),
            "quick_start_title": pick_lang(lang, "快速开始", "Quick start"),
            "quick_start_hint": pick_lang(
                lang,
                "点击复制，粘贴到 Agent 对话框使用",
                "Tap to copy and paste into your Agent chat",
            ),
            "auth_modal_title": pick_lang(lang, "身份认证", "Identity check"),
            "auth_modal_desc": pick_lang(
                lang,
                "请输入访问令牌以解锁个性化设置",
                "Enter your access token to unlock personalized settings",
            ),
            "auth_modal_placeholder": pick_lang(lang, "输入你的访问令牌", "Enter your access token"),
            "auth_modal_hint": pick_lang(lang, "访问令牌有效期 30 天", "Token stays valid for 30 days"),
            "auth_invalid": pick_lang(lang, "访问令牌无效", "Invalid token"),
            "auth_cancel": pick_lang(lang, "取消", "Cancel"),
            "auth_close": pick_lang(lang, "关闭", "Close"),
            "auth_verify": pick_lang(lang, "验证", "Verify"),
            "auth_verify_loading": pick_lang(lang, "验证中...", "Verifying..."),
            "auth_login": pick_lang(lang, "登录", "Login"),
            "auth_enter_token": pick_lang(lang, "请输入访问令牌", "Please enter token"),
            "auth_token_min": pick_lang(
                lang,
                "访问令牌长度不能少于 8 位",
                "Token must be at least 8 characters",
            ),
            "auth_token_max": pick_lang(
                lang,
                "访问令牌长度不能超过 128 位",
                "Token must not exceed 128 characters",
            ),
            "auth_invalid_characters": pick_lang(
                lang,
                "访问令牌包含非法字符",
                "Token contains invalid characters",
            ),
            "auth_verify_failed": pick_lang(
                lang,
                "验证失败，请检查访问令牌是否正确",
                "Verification failed, please check your token",
            ),
            "auth_network_error": pick_lang(
                lang,
                "网络错误，请检查网络连接后重试",
                "Network error, please check your connection and try again",
            ),
            "auth_bad_server_data": pick_lang(lang, "服务器返回无效数据", "The server returned invalid data"),
            "auth_session_active": pick_lang(lang, "会话已连接", "Session active"),
            "auth_expiry_days": pick_lang(lang, "{days} 天后过期", "Expires in {days} days"),
            "show_password": pick_lang(lang, "显示密码", "Show password"),
            "hide_password": pick_lang(lang, "隐藏密码", "Hide password"),
            "toggle_password_visibility": pick_lang(lang, "切换密码可见性", "Toggle password visibility"),
            "user_panel_auth_title": pick_lang(lang, "认证", "Authentication"),
            "user_panel_auth_desc": pick_lang(
                lang,
                "登录后可保存背景设置，并进入你的私人技能库",
                "Sign in to sync preferences and open your private skill library",
            ),
            "user_panel_auth_action": pick_lang(lang, "输入访问令牌", "Enter token"),
            "user_panel_background_label": pick_lang(lang, "背景", "Background"),
            "user_panel_theme_light": pick_lang(lang, "浅色", "Light"),
            "user_panel_theme_dark": pick_lang(lang, "深色", "Dark"),
            "user_panel_logout": pick_lang(lang, "退出登录", "Sign out"),
            "user_menu_anon_label": pick_lang(lang, "登录", "Sign in"),
            "user_menu_logged_label": pick_lang(lang, "已登录用户菜单", "Account menu"),
            "console_session_guest": pick_lang(lang, "登录", "Sign in"),
            "console_session_desc": pick_lang(
                lang,
                "登录后可继续在维护台搜索、检查和处理技能生命周期。",
                "Sign in to keep searching, inspecting, and operating across the skill lifecycle.",
            ),
            "console_session_open_auth": pick_lang(lang, "输入访问令牌", "Enter token"),
            "console_session_label": pick_lang(lang, "当前会话", "Current session"),
            "console_session_role": pick_lang(lang, "角色：{role}", "Role: {role}"),
            "console_session_ready": pick_lang(lang, "会话可用", "Session ready"),
            "logout_success": pick_lang(lang, "已退出登录", "Signed out"),
            "role_maintainer": pick_lang(lang, "维护者", "Maintainer"),
            "role_contributor": pick_lang(lang, "贡献者", "Contributor"),
            "theme_light_name": pick_lang(lang, "浅色主题", "light theme"),
            "theme_dark_name": pick_lang(lang, "深色主题", "dark theme"),
            "theme_switched": pick_lang(lang, "已切换到 {theme}", "Switched to {theme}"),
            "use_skill_ready": pick_lang(
                lang,
                "技能 {name} 已就绪，命令已复制",
                "Skill {name} is ready and the command has been copied",
            ),
            "use_skill_error": pick_lang(lang, "使用技能失败，请重试", "Failed to use skill, please try again"),
            "generic_action_failed": pick_lang(
                lang,
                "操作失败，请刷新页面重试",
                "Action failed, please refresh and try again",
            ),
            "generic_unexpected_error": pick_lang(
                lang,
                "发生错误，请刷新页面重试",
                "An error occurred, please refresh and try again",
            ),
        },
    }


__all__ = [
    "build_kawaii_ui_context",
    "humanize_audience_type",
    "humanize_identifier",
    "humanize_install_mode",
    "humanize_job_kind",
    "humanize_listing_mode",
    "humanize_review_gate",
    "humanize_role",
    "humanize_status",
    "humanize_timestamp",
    "load_json_list",
    "load_json_object",
    "localized_stamp",
    "short_stamp",
]
