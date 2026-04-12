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
            "authenticated": ("已认证", "Authenticated"),
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
            "theme_toggle_label": pick_lang(lang, "切换主题", "Theme switcher"),
            "language_toggle_label": pick_lang(lang, "切换语言", "Language switcher"),
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
            "search_create_command": "scripts/new-skill.sh publisher/my-skill basic",
            "search_install_back": pick_lang(lang, "← 返回", "← Back"),
            "search_install_audience": pick_lang(lang, "受众", "Audience"),
            "search_install_manifest": pick_lang(lang, "清单", "Manifest"),
            "search_install_bundle": pick_lang(lang, "包", "Bundle"),
            "search_install_provenance": pick_lang(lang, "来源", "Provenance"),
            "search_install_signature": pick_lang(lang, "签名", "Signature"),
            "search_install_copy_ref": pick_lang(lang, "复制 install_ref", "Copy install_ref"),
            "search_install_copy_api": pick_lang(lang, "复制 API 路径", "Copy API path"),
            "search_install_open_artifact": pick_lang(lang, "打开产物", "Open artifact"),
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
            "console_auth_modal_title": pick_lang(lang, "身份认证", "Identity check"),
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
            "generic_action_failed": pick_lang(
                lang,
                "操作失败，请刷新页面重试",
                "Action failed, please refresh and try again",
            ),
            "loading": pick_lang(lang, "处理中…", "Processing…"),
            "skill_created": pick_lang(lang, "技能创建成功", "Skill created"),
            "skill_create_error": pick_lang(lang, "创建技能失败", "Failed to create skill"),
            "invalid_json": pick_lang(lang, "JSON 格式错误", "Invalid JSON"),
            "draft_created": pick_lang(lang, "草稿创建成功", "Draft created"),
            "draft_create_error": pick_lang(lang, "创建草稿失败", "Failed to create draft"),
            "draft_saved": pick_lang(lang, "草稿保存成功", "Draft saved"),
            "draft_save_error": pick_lang(lang, "保存草稿失败", "Failed to save draft"),
            "draft_sealed": pick_lang(lang, "草稿已封版", "Draft sealed"),
            "draft_seal_error": pick_lang(lang, "封版失败", "Failed to seal draft"),
            "release_created": pick_lang(lang, "发布创建成功", "Release created"),
            "release_create_error": pick_lang(lang, "创建发布失败", "Failed to create release"),
            "release_ready": pick_lang(lang, "已就绪", "Ready"),
            "release_is_ready": pick_lang(lang, "发布产物已就绪", "Release artifacts are ready"),
            "release_poll_stopped": pick_lang(lang, "状态刷新已停止", "Status refresh stopped"),
            "artifacts_kind": pick_lang(lang, "类型", "Kind"),
            "artifacts_size": pick_lang(lang, "大小", "Size"),
            "artifacts_storage_uri": pick_lang(lang, "存储位置", "Storage URI"),
            "exposure_created": pick_lang(lang, "分享出口创建成功", "Exposure created"),
            "exposure_create_error": pick_lang(lang, "创建分享出口失败", "Failed to create exposure"),
            "exposure_patched": pick_lang(lang, "分享设置已更新", "Exposure settings updated"),
            "exposure_patch_error": pick_lang(lang, "更新分享设置失败", "Failed to update exposure"),
            "exposure_activated": pick_lang(lang, "分享已激活", "Exposure activated"),
            "exposure_activate_error": pick_lang(lang, "激活分享失败", "Failed to activate exposure"),
            "exposure_revoked": pick_lang(lang, "分享已撤销", "Exposure revoked"),
            "exposure_revoke_error": pick_lang(lang, "撤销分享失败", "Failed to revoke exposure"),
            "review_approved": pick_lang(lang, "审核已通过", "Review approved"),
            "review_rejected": pick_lang(lang, "审核已驳回", "Review rejected"),
            "review_commented": pick_lang(lang, "备注已添加", "Comment added"),
            "review_decision_error": pick_lang(lang, "提交审核决定失败", "Failed to submit review decision"),
            "review_detail_history": pick_lang(lang, "详情", "History"),
            "review_detail_error": pick_lang(lang, "加载详情失败", "Failed to load details"),
            "review_detail_hide": pick_lang(lang, "收起", "Hide"),
            "review_empty_label": pick_lang(lang, "暂无决定记录。", "No decisions yet."),
            "review_note_label": pick_lang(lang, "备注", "Note"),
            "review_evidence_label": pick_lang(lang, "证据", "Evidence"),
            "review_requirement_blocking": pick_lang(lang, "阻塞审核", "Blocking review"),
            "review_requirement_none": pick_lang(lang, "无需审核", "No review"),
            "review_hint_prefix": pick_lang(lang, "{audience} exposure 固定使用", "{audience} exposures use"),
            "label_state": pick_lang(lang, "状态", "State"),
            "label_artifacts": pick_lang(lang, "产物", "Artifacts"),
            "search_install_publisher": pick_lang(lang, "发布者 / Publisher", "Publisher / 发布者"),
            "search_install_install_scope": pick_lang(lang, "安装范围 / Install Scope", "Install Scope / 安装范围"),
            "search_install_listing_mode": pick_lang(lang, "列出模式 / Listing Mode", "Listing Mode / 列出模式"),
            "search_install_runtime": pick_lang(lang, "运行时 / Runtime", "Runtime / 运行时"),
            "search_install_readiness": pick_lang(lang, "就绪状态 / Readiness", "Readiness / 就绪状态"),
            "search_install_workspace_targets": pick_lang(lang, "工作区目标 / Workspace Targets", "Workspace Targets / 工作区目标"),
            "search_install_bundle_sha256": pick_lang(lang, "包 SHA256 / Bundle SHA256", "Bundle SHA256 / 包 SHA256"),
            "access_load_failed": pick_lang(lang, "加载失败 / Failed", "Failed / 加载失败"),
            "label_principal": pick_lang(lang, "主体 / Principal", "Principal / 主体"),
            "label_username": pick_lang(lang, "用户名 / Username", "Username / 用户名"),
            "label_scopes": pick_lang(lang, "作用域 / Scopes", "Scopes / 作用域"),
            "access_me_error": pick_lang(lang, "无法加载身份信息 / Unable to load identity", "Unable to load identity / 无法加载身份信息"),
            "access_input_required": pick_lang(lang, "请输入发布 ID / Please enter Release ID", "Please enter Release ID / 请输入发布 ID"),
            "access_ok": pick_lang(lang, "有访问权限", "Access granted"),
            "label_ok": pick_lang(lang, "状态 / ok", "ok / 状态"),
            "label_credential_type": pick_lang(lang, "凭证类型 / credential_type", "credential_type / 凭证类型"),
            "label_principal_id": pick_lang(lang, "主体 ID / principal_id", "principal_id / 主体 ID"),
            "label_scope_granted": pick_lang(lang, "授权范围 / scope_granted", "scope_granted / 授权范围"),
            "access_denied": pick_lang(lang, "无访问权限 / Access denied", "Access denied / 无访问权限"),
            "access_check_error": pick_lang(lang, "检查失败 / Check failed", "Check failed / 检查失败"),
            "table_col_id": pick_lang(lang, "ID", "ID"),
            "table_col_type": pick_lang(lang, "类型", "Type"),
            "table_col_kind": pick_lang(lang, "类型", "Kind"),
            "table_col_principal": pick_lang(lang, "主体", "Principal"),
            "table_col_scopes": pick_lang(lang, "作用域", "Scopes"),
            "table_col_grant": pick_lang(lang, "授权", "Grant"),
            "table_col_release": pick_lang(lang, "关联发布", "Release"),
            "table_col_expires": pick_lang(lang, "过期时间", "Expires"),
            "table_col_last_used": pick_lang(lang, "最后使用", "Last used"),
            "table_col_subject": pick_lang(lang, "对象", "Subject"),
            "table_col_audience": pick_lang(lang, "可见范围", "Audience"),
            "table_col_state": pick_lang(lang, "状态", "State"),
            "table_col_size": pick_lang(lang, "大小", "Size"),
            "table_col_storage_uri": pick_lang(lang, "存储位置", "Storage URI"),
            "table_col_listing": pick_lang(lang, "列出策略", "Listing"),
            "table_col_open": pick_lang(lang, "跳转", "Open"),
            "table_col_skill": pick_lang(lang, "技能", "Skill"),
            "table_col_mode": pick_lang(lang, "模式", "Mode"),
            "table_col_opened": pick_lang(lang, "打开时间", "Opened"),
            "table_col_actions": pick_lang(lang, "操作", "Actions"),
            "table_col_install": pick_lang(lang, "安装", "Install"),
            "table_col_review_requirement": pick_lang(lang, "审核要求", "Review requirement"),
            "table_col_review_state": pick_lang(lang, "审核状态", "Review state"),
            "table_col_content_ref": pick_lang(lang, "内容引用", "Content ref"),
            "table_col_updated": pick_lang(lang, "更新时间", "Updated"),
            "table_col_version": pick_lang(lang, "版本号", "Version"),
            "table_col_version_short": pick_lang(lang, "版本", "Version"),
            "table_col_created": pick_lang(lang, "创建时间", "Created"),
            "table_col_ready": pick_lang(lang, "就绪时间", "Ready"),
            "table_col_namespace": pick_lang(lang, "命名空间", "Namespace"),
            "table_col_drafts_versions_releases": pick_lang(lang, "草稿 / 版本 / 发布", "Drafts / Versions / Releases"),
            "table_col_default_visibility": pick_lang(lang, "默认可见性", "Default visibility"),
            "table_col_entrypoint": pick_lang(lang, "入口文件", "Entrypoint"),
            "table_col_share_exits": pick_lang(lang, "分享出口", "Share exits"),
            "table_col_listing_install": pick_lang(lang, "列出 / 安装", "Listing / Install"),
            "table_col_review": pick_lang(lang, "审核", "Review"),
            "empty_review_cases": pick_lang(lang, "还没有审核单。", "No review cases yet."),
            "section_drafts": pick_lang(lang, "草稿", "Drafts"),
            "section_releases": pick_lang(lang, "发布", "Releases"),
            "section_versions": pick_lang(lang, "版本", "Versions"),
            "option_public": pick_lang(lang, "公开", "Public"),
            "option_private": pick_lang(lang, "私人", "Private"),
            "option_authenticated": pick_lang(lang, "已认证", "Authenticated"),
            "option_grant": pick_lang(lang, "令牌共享", "Shared by token"),
            "action_share": pick_lang(lang, "分享", "Share"),
            "action_detail": pick_lang(lang, "详情", "Detail"),
            "action_back_to_release": pick_lang(lang, "返回发布", "Back to release"),
            "action_back_to_skill": pick_lang(lang, "返回技能", "Back to skill"),
            "action_check": pick_lang(lang, "检查", "Check"),
            "action_edit": pick_lang(lang, "编辑", "Edit"),
            "action_seal": pick_lang(lang, "封版", "Seal"),
            "action_create_release": pick_lang(lang, "创建发布", "Create release"),
            "badge_release_access_check": pick_lang(lang, "发布访问检查", "Release access check"),
            "badge_access_control": pick_lang(lang, "访问控制", "Access control"),
            "badge_current_identity": pick_lang(lang, "当前身份", "Current identity"),
            "badge_draft_detail": pick_lang(lang, "草稿详情", "Draft detail"),
            "badge_edit_draft": pick_lang(lang, "编辑草稿", "Edit draft"),
            "badge_lifecycle_overview": pick_lang(lang, "生命周期总览", "Lifecycle overview"),
            "badge_skill_detail": pick_lang(lang, "技能详情", "Skill detail"),
            "badge_access_denied": pick_lang(lang, "访问受限", "Access denied"),
            "badge_token_auth": pick_lang(lang, "令牌认证", "Token Auth"),
            "badge_review_inbox": pick_lang(lang, "审核收件箱", "Review inbox"),
            "badge_release_runtime_readiness": pick_lang(lang, "发布运行时就绪", "Release runtime readiness"),
            "badge_release_detail": pick_lang(lang, "发布详情", "Release detail"),
            "badge_historical_compatibility": pick_lang(lang, "历史兼容性上下文", "Historical compatibility context"),
            "badge_create_draft": pick_lang(lang, "创建草稿", "Create draft"),
            "badge_create_skill": pick_lang(lang, "创建技能", "Create skill"),
            "badge_create_exposure": pick_lang(lang, "创建分享出口", "Create exposure"),
            "badge_share_detail": pick_lang(lang, "分享详情", "Share detail"),
            "text_loading": pick_lang(lang, "加载中…", "Loading…"),
            "action_approve": pick_lang(lang, "通过", "Approve"),
            "action_reject": pick_lang(lang, "驳回", "Reject"),
            "action_comment": pick_lang(lang, "备注", "Comment"),
            "option_listed": pick_lang(lang, "可列出", "Listed"),
            "option_direct_only": pick_lang(lang, "仅直达", "Direct only"),
            "option_install_enabled": pick_lang(lang, "允许安装", "Install enabled"),
            "option_install_disabled": pick_lang(lang, "禁止安装", "Install disabled"),
            "option_no_review": pick_lang(lang, "无需审核", "No review"),
            "option_advisory_review": pick_lang(lang, "建议审核", "Advisory review"),
            "option_blocking_review": pick_lang(lang, "阻塞审核", "Blocking review"),
            "label_runtime_readiness": pick_lang(lang, "运行时就绪", "Runtime readiness"),
            "label_runtime_platform": pick_lang(lang, "运行时平台", "Runtime platform"),
            "label_blocking_platforms": pick_lang(lang, "阻塞平台", "Blocking platforms"),
            "text_none": pick_lang(lang, "无阻塞", "None"),
            "label_audience": pick_lang(lang, "可见范围", "Audience"),
            "label_listing_mode": pick_lang(lang, "列出策略", "Listing mode"),
            "label_install_mode": pick_lang(lang, "安装模式", "Install mode"),
            "label_review_mode": pick_lang(lang, "审核模式", "Review mode"),
            "text_materializing": pick_lang(lang, "产物生成中，请稍候…", "Materializing, please wait…"),
            "label_format_version": pick_lang(lang, "格式版本", "Format version"),
            "label_created_at": pick_lang(lang, "创建时间", "Created at"),
            "login_badge": pick_lang(lang, "令牌认证", "Token Auth"),
            "login_title": pick_lang(lang, "登录", "Login"),
            "login_desc": pick_lang(lang, "登录后可进入你的私人技能库，查看技能、草稿、发布、分享和访问令牌。", "Sign in to enter your private skill library and inspect skills, drafts, releases, sharing, and access tokens."),
            "login_input_label": pick_lang(lang, "输入访问令牌", "Enter Access Token"),
            "login_placeholder": pick_lang(lang, "输入你的访问令牌", "Enter your access token"),
            "login_aria_label": pick_lang(lang, "访问令牌", "Access token"),
            "toggle_password_title": pick_lang(lang, "显示/隐藏密码", "Show/Hide password"),
            "login_hint": pick_lang(lang, "访问令牌可在个人账户设置中获取", "Token can be found in account settings"),
            "login_button": pick_lang(lang, "登录", "Login"),
            "empty_skills": pick_lang(lang, "还没有技能。", "No skills yet."),
            "empty_drafts": pick_lang(lang, "还没有草稿。", "No drafts yet."),
            "empty_releases": pick_lang(lang, "还没有发布。", "No releases yet."),
            "empty_tokens": pick_lang(lang, "还没有令牌。", "No tokens yet."),
            "empty_grants": pick_lang(lang, "还没有 grant。", "No grants yet."),
            "empty_artifacts": pick_lang(lang, "还没有产物。", "No artifacts yet."),
            "empty_share_exits": pick_lang(lang, "还没有分享出口。", "No share exits yet."),
            "empty_share_entries": pick_lang(lang, "还没有可见性出口。", "No share entries yet."),
            "empty_audience_exits": pick_lang(lang, "还没有可见性出口。", "No audience exits."),
            "empty_no_drafts": pick_lang(lang, "没有草稿。", "No drafts."),
            "empty_no_sealed": pick_lang(lang, "没有封版记录。", "No sealed versions."),
            "empty_no_releases": pick_lang(lang, "没有发布记录。", "No releases."),
            "badge_grant_records": pick_lang(lang, "授权记录", "Grant records"),
            "badge_seal_draft": pick_lang(lang, "封版", "Seal draft"),
            "badge_metadata_snapshot": pick_lang(lang, "元数据快照", "Metadata snapshot"),
            "label_base_version": pick_lang(lang, "基线版本", "Base version"),
            "label_sha256": pick_lang(lang, "SHA256", "SHA256"),
            "label_release_id": pick_lang(lang, "发布 ID", "Release ID"),
            "label_summary": pick_lang(lang, "摘要", "Summary"),
            "label_install_ref": pick_lang(lang, "Install ref", "Install ref"),
            "label_bundle_url": pick_lang(lang, "Bundle URL", "Bundle URL"),
            "label_manifest_url": pick_lang(lang, "Manifest URL", "Manifest URL"),
            "label_runtime_signature": pick_lang(lang, "Runtime signature", "Runtime signature"),
            "label_freshness": pick_lang(lang, "Freshness", "Freshness"),
            "label_canonical_runtime": pick_lang(lang, "Canonical runtime", "Canonical runtime"),
            "label_exposures": pick_lang(lang, "可见性出口", "Exposures"),
            "action_open_skill": pick_lang(lang, "返回技能", "Open skill"),
            "action_access_page": pick_lang(lang, "访问页", "Access"),
            "action_review_page": pick_lang(lang, "审核页", "Review"),
            "action_new_draft": pick_lang(lang, "新建草稿", "New draft"),
            "action_new_release": pick_lang(lang, "新建发布", "New release"),
            "action_activate": pick_lang(lang, "激活", "Activate"),
            "action_revoke": pick_lang(lang, "撤销", "Revoke"),
            "action_patch": pick_lang(lang, "修改", "Patch"),
            "hint_lifecycle": pick_lang(lang, "先写，再封版，再发布", "Draft, seal, then release"),
            "hint_lifecycle_desc": pick_lang(lang, "技能、草稿、发布、分享和访问令牌已经拆成独立领域对象，后续扩展审核、授权和安装规则时不必再修改同一张大表。", "Skills, drafts, releases, sharing, and access tokens now live as separate domain objects so review, authorization, and install rules can evolve without reshaping one giant table."),
            "hint_access_review": pick_lang(lang, "查看访问与审核", "Open access and review"),
            "hint_access_review_desc": pick_lang(lang, "令牌和 grant 放在访问页，公开暴露的审核单放在审核页。", "Tokens and grants live on the access page, while public exposure review cases live in the review inbox."),
            "hint_seal": pick_lang(lang, "封版后草稿将变为只读，并生成不可变版本。", "Sealing makes the draft read-only and creates an immutable version."),
            "hint_review_cases": pick_lang(lang, "公开 exposure 会自动打开审核单。这样作者仍然可以自由发布私人版本，而公开版本必须通过额外 gate。", "Public exposures automatically open review cases. Authors can still ship private versions freely, while public versions pass through an extra gate."),
            "hint_access_tokens": pick_lang(lang, "token 和 grant 已经从技能生命周期里拆开。技能负责内容，exposure 负责谁能看，credential 负责谁能用哪个 token。", "Tokens and grants are now separate from the skill lifecycle. Skills carry content, exposures describe who can see it, and credentials decide who can use which token."),
            "hint_draft_editable": pick_lang(lang, "草稿是可编辑态，封版后会进入不可变版本。", "Drafts stay editable until they are sealed into immutable versions."),
            "hint_release_runtime": pick_lang(lang, "同一个 release 可以同时保留私人、令牌共享和公开三种出口，彼此不互相覆盖。", "One release can keep private, token-shared, and public audiences side by side without one replacing another."),
            "placeholder_slug": pick_lang(lang, "my-skill", "my-skill"),
            "placeholder_display_name": pick_lang(lang, "My Skill", "My Skill"),
            "placeholder_summary": pick_lang(lang, "一句话描述", "One line summary"),
            "aria_main_content": pick_lang(lang, "主内容", "Main content"),
            "aria_primary_navigation": pick_lang(lang, "主导航", "Primary navigation"),
            "aria_search_results": pick_lang(lang, "搜索结果", "Search results"),
            "skip_to_main_content": pick_lang(lang, "跳转到主内容", "Skip to main content"),
            "meta_description": pick_lang(lang, "infinitas - 小二的私人技能库，覆盖技能创作、发布、分享与安装", "infinitas - a private-first agent skill library for authoring, release, sharing, and install"),
            "section_review_cases": pick_lang(lang, "审核单", "Review cases"),
            "section_review": pick_lang(lang, "审核", "Review"),
            "section_audience_exits": pick_lang(lang, "可见性出口", "Audience exits"),
            "section_share_exits": pick_lang(lang, "分享出口", "Share exits"),
            "section_share": pick_lang(lang, "分享", "Share"),
            "section_tokens": pick_lang(lang, "令牌", "Tokens"),
            "section_artifacts": pick_lang(lang, "产物", "Artifacts"),
            "label_verified_support": pick_lang(lang, "已验证支持", "Verified support"),
            "label_historical_platforms": pick_lang(lang, "历史平台", "Historical platforms"),
            "label_grant_count": pick_lang(lang, "授权数", "Grant"),
            "label_release_short": pick_lang(lang, "发布", "Release"),
            "label_visibility": pick_lang(lang, "默认可见性", "Visibility"),
            "label_status": pick_lang(lang, "状态", "Status"),
            "label_slug": pick_lang(lang, "标识", "Slug"),
            "label_slug_with_hint": pick_lang(lang, "标识 (slug)", "Slug"),
            "label_display_name": pick_lang(lang, "显示名称", "Display name"),
            "label_metadata_json": pick_lang(lang, "元数据 JSON", "Metadata JSON"),
            "label_ready_at": pick_lang(lang, "就绪时间", "Ready at"),
            "action_share_page": pick_lang(lang, "分享页", "Share page"),
            "action_open_release": pick_lang(lang, "查看发布", "Open release"),
            "action_open_skill_short": pick_lang(lang, "查看技能", "Open skill"),
            "action_share_settings": pick_lang(lang, "分享设置", "Share settings"),
            "action_save_draft": pick_lang(lang, "保存草稿", "Save draft"),
            "action_confirm_seal": pick_lang(lang, "确认封版", "Seal draft"),
            "action_update": pick_lang(lang, "更新", "Update"),
            "action_history": pick_lang(lang, "详情", "History"),
            "action_copy_command": pick_lang(lang, "复制命令", "Copy command"),
            "action_copy": pick_lang(lang, "复制", "Copy"),
            "hint_release_immutable": pick_lang(lang, "发布是不可变交付物，后续分享只是在 release 外侧叠加 audience 策略。", "A release is immutable; later sharing only adds audience policies around the release."),
            "hint_public_review_required": pick_lang(lang, "公开 exposure 会自动进入阻塞审核流程，需要审核通过后才能激活。", "Public exposure requires a blocking review before activation."),
            "hint_activation_blocked": pick_lang(lang, "暂时无法激活", "Activation blocked"),
            "hint_activation_blocked_not_approved": pick_lang(lang, "审核未通过，无法激活", "Activation blocked: review was not approved"),
            "hint_activation_blocked_rejected": pick_lang(lang, "审核已被驳回，无法激活", "Activation blocked: review was rejected"),
            "hint_activation_blocked_review_required": pick_lang(lang, "需要审核通过后才能激活", "Activation blocked: review must be approved first"),
            "option_blocking": pick_lang(lang, "阻塞审核", "Blocking"),
            "option_advisory": pick_lang(lang, "建议审核", "Advisory"),
            "option_enabled": pick_lang(lang, "允许安装", "Enabled"),
            "option_disabled": pick_lang(lang, "禁止安装", "Disabled"),
            "placeholder_review_note": pick_lang(lang, "备注（可选）", "Note (optional)"),
            "aria_review_note": pick_lang(lang, "审核备注", "Review note"),
            "login_error": pick_lang(lang, "访问令牌无效", "Token invalid"),
            "page_kicker_fallback": pick_lang(lang, "运行中", "Running"),
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
