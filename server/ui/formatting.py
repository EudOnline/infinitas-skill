from __future__ import annotations

import json
from datetime import datetime

from fastapi import Request

from server.auth import AUTH_COOKIE_NAME
from server.ui.i18n import build_language_switches, pick_lang, t, with_lang


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
        return t(lang, "localized_stamp_fallback")
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


def humanize_object_kind(kind: str | None, lang: str) -> str:
    return _humanize_with_mapping(
        kind,
        lang,
        {
            "skill": ("技能", "Skill"),
            "agent_preset": ("Agent 预设", "Agent preset"),
            "agent_code": ("Agent 代码", "Agent code"),
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
            {"value": "light", "label": t(lang, "theme.light")},
            {"value": "dark", "label": t(lang, "theme.dark")},
        ],
        "ui": {
            "brand_subtitle": t(lang, "brand_subtitle"),
            "theme_toggle_label": t(lang, "theme_toggle_label"),
            "language_toggle_label": t(lang, "language_toggle_label"),
            "copy_success": t(lang, "copy_success"),
            "copy_error": t(lang, "copy_error"),
            "toast_close": t(lang, "toast_close"),
            "copy_icon_title": t(lang, "copy_icon_title"),
            "copy_button_label": t(lang, "copy_button_label"),
            "status_running": t(lang, "status_running"),
            "search_placeholder": t(lang, "search_placeholder"),
            "search_results_label": t(lang, "search_results_label"),
            "search_skills_label": t(lang, "search_skills_label"),
            "search_commands_label": t(lang, "search_commands_label"),
            "search_empty_label": t(lang, "search_empty_label"),
            "search_create_label": t(lang, "search_create_label"),
            "search_create_command": "scripts/new-skill.sh publisher/my-skill basic",
            "search_install_back": t(lang, "search_install_back"),
            "search_install_audience": t(lang, "search_install_audience"),
            "search_install_manifest": t(lang, "search_install_manifest"),
            "search_install_bundle": t(lang, "search_install_bundle"),
            "search_install_provenance": t(lang, "search_install_provenance"),
            "search_install_signature": t(lang, "search_install_signature"),
            "search_install_copy_ref": t(lang, "search_install_copy_ref"),
            "search_install_copy_api": t(lang, "search_install_copy_api"),
            "search_install_open_artifact": t(lang, "search_install_open_artifact"),
            "search_auth_required": t(lang, "search_auth_required"),
            "page_kicker": page_kicker,
            "page_eyebrow": page_eyebrow,
            "handoff_title": t(lang, "handoff_title"),
            "handoff_human_tab": t(lang, "handoff_human_tab"),
            "handoff_agent_tab": t(lang, "handoff_agent_tab"),
            "copy_prompt_action": t(lang, "copy_prompt_action"),
            "cli_mirror_label": t(lang, "cli_mirror_label"),
            "console_section_title": t(lang, "console_section_title"),
            "skills_section_title": t(lang, "skills_section_title"),
            "skills_section_subtitle": t(lang, "skills_section_subtitle"),
            "featured_skill_fallback": t(lang, "featured_skill_fallback"),
            "copy_inspect_action": t(lang, "copy_inspect_action"),
            "go_handoff_action": t(lang, "go_handoff_action"),
            "quick_start_title": t(lang, "quick_start_title"),
            "quick_start_hint": t(lang, "quick_start_hint"),
            "auth_modal_title": t(lang, "auth_modal_title"),
            "console_auth_modal_title": t(lang, "console_auth_modal_title"),
            "auth_modal_desc": t(lang, "auth_modal_desc"),
            "auth_modal_placeholder": t(lang, "auth_modal_placeholder"),
            "auth_modal_hint": t(lang, "auth_modal_hint"),
            "auth_invalid": t(lang, "auth_invalid"),
            "auth_cancel": t(lang, "auth_cancel"),
            "auth_close": t(lang, "auth_close"),
            "auth_verify": t(lang, "auth_verify"),
            "auth_verify_loading": t(lang, "auth_verify_loading"),
            "auth_login": t(lang, "auth_login"),
            "auth_enter_token": t(lang, "auth_enter_token"),
            "auth_token_min": t(lang, "auth_token_min"),
            "auth_token_max": t(lang, "auth_token_max"),
            "auth_invalid_characters": t(lang, "auth_invalid_characters"),
            "auth_verify_failed": t(lang, "auth_verify_failed"),
            "auth_network_error": t(lang, "auth_network_error"),
            "auth_bad_server_data": t(lang, "auth_bad_server_data"),
            "auth_session_active": t(lang, "auth_session_active"),
            "auth_expiry_days": t(lang, "auth_expiry_days"),
            "show_password": t(lang, "show_password"),
            "hide_password": t(lang, "hide_password"),
            "toggle_password_visibility": t(lang, "toggle_password_visibility"),
            "user_panel_auth_title": t(lang, "user_panel_auth_title"),
            "user_panel_auth_desc": t(lang, "user_panel_auth_desc"),
            "user_panel_auth_action": t(lang, "user_panel_auth_action"),
            "user_panel_background_label": t(lang, "user_panel_background_label"),
            "user_panel_theme_light": t(lang, "user_panel_theme_light"),
            "user_panel_theme_dark": t(lang, "user_panel_theme_dark"),
            "user_panel_logout": t(lang, "user_panel_logout"),
            "user_menu_anon_label": t(lang, "user_menu_anon_label"),
            "user_menu_logged_label": t(lang, "user_menu_logged_label"),
            "console_session_guest": t(lang, "console_session_guest"),
            "console_session_desc": t(lang, "console_session_desc"),
            "console_session_open_auth": t(lang, "console_session_open_auth"),
            "console_session_label": t(lang, "console_session_label"),
            "console_session_role": t(lang, "console_session_role"),
            "console_session_ready": t(lang, "console_session_ready"),
            "logout_success": t(lang, "logout_success"),
            "role_maintainer": t(lang, "role_maintainer"),
            "role_contributor": t(lang, "role_contributor"),
            "theme_light_name": t(lang, "theme_light_name"),
            "theme_dark_name": t(lang, "theme_dark_name"),
            "theme_switched": t(lang, "theme_switched"),
            "generic_action_failed": t(lang, "generic_action_failed"),
            "loading": t(lang, "loading"),
            "skill_created": t(lang, "skill_created"),
            "skill_create_error": t(lang, "skill_create_error"),
            "invalid_json": t(lang, "invalid_json"),
            "draft_created": t(lang, "draft_created"),
            "draft_create_error": t(lang, "draft_create_error"),
            "draft_saved": t(lang, "draft_saved"),
            "draft_save_error": t(lang, "draft_save_error"),
            "draft_sealed": t(lang, "draft_sealed"),
            "draft_seal_error": t(lang, "draft_seal_error"),
            "release_created": t(lang, "release_created"),
            "release_create_error": t(lang, "release_create_error"),
            "release_ready": t(lang, "release_ready"),
            "release_is_ready": t(lang, "release_is_ready"),
            "release_poll_stopped": t(lang, "release_poll_stopped"),
            "artifacts_kind": t(lang, "artifacts_kind"),
            "artifacts_size": t(lang, "artifacts_size"),
            "artifacts_storage_uri": t(lang, "artifacts_storage_uri"),
            "exposure_created": t(lang, "exposure_created"),
            "exposure_create_error": t(lang, "exposure_create_error"),
            "exposure_patched": t(lang, "exposure_patched"),
            "exposure_patch_error": t(lang, "exposure_patch_error"),
            "exposure_activated": t(lang, "exposure_activated"),
            "exposure_activate_error": t(lang, "exposure_activate_error"),
            "exposure_revoked": t(lang, "exposure_revoked"),
            "exposure_revoke_error": t(lang, "exposure_revoke_error"),
            "review_approved": t(lang, "review_approved"),
            "review_rejected": t(lang, "review_rejected"),
            "review_commented": t(lang, "review_commented"),
            "review_decision_error": t(lang, "review_decision_error"),
            "review_detail_history": t(lang, "review_detail_history"),
            "review_detail_error": t(lang, "review_detail_error"),
            "review_detail_hide": t(lang, "review_detail_hide"),
            "review_empty_label": t(lang, "review_empty_label"),
            "review_note_label": t(lang, "review_note_label"),
            "review_evidence_label": t(lang, "review_evidence_label"),
            "review_requirement_blocking": t(lang, "review_requirement_blocking"),
            "review_requirement_none": t(lang, "review_requirement_none"),
            "review_hint_prefix": t(lang, "review_hint_prefix"),
            "label_state": t(lang, "label_state"),
            "label_artifacts": t(lang, "label_artifacts"),
            "search_install_publisher": t(lang, "search_install_publisher"),
            "search_install_install_scope": t(lang, "search_install_install_scope"),
            "search_install_listing_mode": t(lang, "search_install_listing_mode"),
            "search_install_runtime": t(lang, "search_install_runtime"),
            "search_install_readiness": t(lang, "search_install_readiness"),
            "search_install_workspace_targets": t(lang, "search_install_workspace_targets"),
            "search_install_bundle_sha256": t(lang, "search_install_bundle_sha256"),
            "access_load_failed": t(lang, "access_load_failed"),
            "label_principal": t(lang, "label_principal"),
            "label_username": t(lang, "label_username"),
            "label_scopes": t(lang, "label_scopes"),
            "access_me_error": t(lang, "access_me_error"),
            "access_input_required": t(lang, "access_input_required"),
            "access_ok": t(lang, "access_ok"),
            "label_ok": t(lang, "label_ok"),
            "label_credential_type": t(lang, "label_credential_type"),
            "label_principal_id": t(lang, "label_principal_id"),
            "label_scope_granted": t(lang, "label_scope_granted"),
            "access_denied": t(lang, "access_denied"),
            "access_check_error": t(lang, "access_check_error"),
            "table_col_id": t(lang, "table_col_id"),
            "table_col_type": t(lang, "table_col_type"),
            "table_col_kind": t(lang, "table_col_kind"),
            "table_col_principal": t(lang, "table_col_principal"),
            "table_col_scopes": t(lang, "table_col_scopes"),
            "table_col_identity": t(lang, "table_col_identity"),
            "table_col_timing": t(lang, "table_col_timing"),
            "table_col_grant": t(lang, "table_col_grant"),
            "table_col_release": t(lang, "table_col_release"),
            "table_col_expires": t(lang, "table_col_expires"),
            "table_col_last_used": t(lang, "table_col_last_used"),
            "table_col_subject": t(lang, "table_col_subject"),
            "table_col_audience": t(lang, "table_col_audience"),
            "table_col_state": t(lang, "table_col_state"),
            "table_col_size": t(lang, "table_col_size"),
            "table_col_storage_uri": t(lang, "table_col_storage_uri"),
            "table_col_listing": t(lang, "table_col_listing"),
            "table_col_open": t(lang, "table_col_open"),
            "table_col_skill": t(lang, "table_col_skill"),
            "table_col_mode": t(lang, "table_col_mode"),
            "table_col_opened": t(lang, "table_col_opened"),
            "table_col_actions": t(lang, "table_col_actions"),
            "table_col_install": t(lang, "table_col_install"),
            "table_col_review_requirement": t(lang, "table_col_review_requirement"),
            "table_col_review_state": t(lang, "table_col_review_state"),
            "table_col_content_ref": t(lang, "table_col_content_ref"),
            "table_col_updated": t(lang, "table_col_updated"),
            "table_col_version": t(lang, "table_col_version"),
            "table_col_version_short": t(lang, "table_col_version_short"),
            "table_col_created": t(lang, "table_col_created"),
            "table_col_ready": t(lang, "table_col_ready"),
            "table_col_namespace": t(lang, "table_col_namespace"),
            "table_col_drafts_versions_releases": t(lang, "table_col_drafts_versions_releases"),
            "table_col_default_visibility": t(lang, "table_col_default_visibility"),
            "table_col_entrypoint": t(lang, "table_col_entrypoint"),
            "table_col_share_exits": t(lang, "table_col_share_exits"),
            "table_col_listing_install": t(lang, "table_col_listing_install"),
            "table_col_review": t(lang, "table_col_review"),
            "empty_review_cases": t(lang, "empty_review_cases"),
            "section_drafts": t(lang, "section_drafts"),
            "section_releases": t(lang, "section_releases"),
            "section_versions": t(lang, "section_versions"),
            "option_public": t(lang, "option_public"),
            "option_private": t(lang, "option_private"),
            "option_authenticated": t(lang, "option_authenticated"),
            "option_grant": t(lang, "option_grant"),
            "action_share": t(lang, "action_share"),
            "action_detail": t(lang, "action_detail"),
            "action_back_to_release": t(lang, "action_back_to_release"),
            "action_back_to_skill": t(lang, "action_back_to_skill"),
            "action_check": t(lang, "action_check"),
            "action_edit": t(lang, "action_edit"),
            "action_seal": t(lang, "action_seal"),
            "action_create_release": t(lang, "action_create_release"),
            "badge_release_access_check": t(lang, "badge_release_access_check"),
            "badge_access_control": t(lang, "badge_access_control"),
            "badge_current_identity": t(lang, "badge_current_identity"),
            "badge_draft_detail": t(lang, "badge_draft_detail"),
            "badge_edit_draft": t(lang, "badge_edit_draft"),
            "badge_lifecycle_overview": t(lang, "badge_lifecycle_overview"),
            "badge_skill_detail": t(lang, "badge_skill_detail"),
            "badge_access_denied": t(lang, "badge_access_denied"),
            "badge_token_auth": t(lang, "badge_token_auth"),
            "badge_review_inbox": t(lang, "badge_review_inbox"),
            "badge_release_runtime_readiness": t(lang, "badge_release_runtime_readiness"),
            "badge_release_detail": t(lang, "badge_release_detail"),
            "badge_historical_compatibility": t(lang, "badge_historical_compatibility"),
            "badge_create_draft": t(lang, "badge_create_draft"),
            "badge_create_skill": t(lang, "badge_create_skill"),
            "badge_create_exposure": t(lang, "badge_create_exposure"),
            "badge_share_detail": t(lang, "badge_share_detail"),
            "text_loading": t(lang, "text_loading"),
            "action_approve": t(lang, "action_approve"),
            "action_reject": t(lang, "action_reject"),
            "action_review": t(lang, "action_review"),
            "action_comment": t(lang, "action_comment"),
            "option_listed": t(lang, "option_listed"),
            "option_direct_only": t(lang, "option_direct_only"),
            "option_install_enabled": t(lang, "option_install_enabled"),
            "option_install_disabled": t(lang, "option_install_disabled"),
            "option_no_review": t(lang, "option_no_review"),
            "option_advisory_review": t(lang, "option_advisory_review"),
            "option_blocking_review": t(lang, "option_blocking_review"),
            "label_runtime_readiness": t(lang, "label_runtime_readiness"),
            "label_runtime_platform": t(lang, "label_runtime_platform"),
            "label_blocking_platforms": t(lang, "label_blocking_platforms"),
            "text_none": t(lang, "text_none"),
            "label_audience": t(lang, "label_audience"),
            "label_listing_mode": t(lang, "label_listing_mode"),
            "label_install_mode": t(lang, "label_install_mode"),
            "label_review_mode": t(lang, "label_review_mode"),
            "text_materializing": t(lang, "text_materializing"),
            "label_format_version": t(lang, "label_format_version"),
            "label_created_at": t(lang, "label_created_at"),
            "login_badge": t(lang, "login_badge"),
            "login_title": t(lang, "login_title"),
            "login_desc": t(lang, "login_desc"),
            "login_input_label": t(lang, "login_input_label"),
            "login_placeholder": t(lang, "login_placeholder"),
            "login_aria_label": t(lang, "login_aria_label"),
            "toggle_password_title": t(lang, "toggle_password_title"),
            "login_hint": t(lang, "login_hint"),
            "login_button": t(lang, "login_button"),
            "empty_skills": t(lang, "empty_skills"),
            "empty_drafts": t(lang, "empty_drafts"),
            "empty_releases": t(lang, "empty_releases"),
            "empty_tokens": t(lang, "empty_tokens"),
            "empty_grants": t(lang, "empty_grants"),
            "empty_artifacts": t(lang, "empty_artifacts"),
            "empty_share_exits": t(lang, "empty_share_exits"),
            "empty_share_entries": t(lang, "empty_share_entries"),
            "empty_audience_exits": t(lang, "empty_audience_exits"),
            "empty_no_drafts": t(lang, "empty_no_drafts"),
            "empty_no_sealed": t(lang, "empty_no_sealed"),
            "empty_no_releases": t(lang, "empty_no_releases"),
            "badge_grant_records": t(lang, "badge_grant_records"),
            "badge_seal_draft": t(lang, "badge_seal_draft"),
            "badge_metadata_snapshot": t(lang, "badge_metadata_snapshot"),
            "label_base_version": t(lang, "label_base_version"),
            "label_sha256": t(lang, "label_sha256"),
            "label_release_id": t(lang, "label_release_id"),
            "label_summary": t(lang, "label_summary"),
            "label_install_ref": t(lang, "label_install_ref"),
            "label_bundle_url": t(lang, "label_bundle_url"),
            "label_manifest_url": t(lang, "label_manifest_url"),
            "label_runtime_signature": t(lang, "label_runtime_signature"),
            "label_freshness": t(lang, "label_freshness"),
            "label_canonical_runtime": t(lang, "label_canonical_runtime"),
            "label_exposures": t(lang, "label_exposures"),
            "action_open_skill": t(lang, "action_open_skill"),
            "action_access_page": t(lang, "action_access_page"),
            "action_review_page": t(lang, "action_review_page"),
            "action_new_draft": t(lang, "action_new_draft"),
            "action_new_release": t(lang, "action_new_release"),
            "action_activate": t(lang, "action_activate"),
            "action_revoke": t(lang, "action_revoke"),
            "action_patch": t(lang, "action_patch"),
            "hint_lifecycle": t(lang, "hint_lifecycle"),
            "hint_lifecycle_desc": t(lang, "hint_lifecycle_desc"),
            "hint_access_review": t(lang, "hint_access_review"),
            "hint_access_review_desc": t(lang, "hint_access_review_desc"),
            "hint_seal": t(lang, "hint_seal"),
            "hint_review_cases": t(lang, "hint_review_cases"),
            "hint_access_tokens": t(lang, "hint_access_tokens"),
            "hint_draft_editable": t(lang, "hint_draft_editable"),
            "hint_release_runtime": t(lang, "hint_release_runtime"),
            "placeholder_slug": t(lang, "placeholder_slug"),
            "placeholder_display_name": t(lang, "placeholder_display_name"),
            "placeholder_summary": t(lang, "placeholder_summary"),
            "aria_main_content": t(lang, "aria_main_content"),
            "aria_primary_navigation": t(lang, "aria_primary_navigation"),
            "search_aria_label": t(lang, "search_aria_label"),
            "aria_search_results": t(lang, "aria_search_results"),
            "skip_to_main_content": t(lang, "skip_to_main_content"),
            "meta_description": t(lang, "meta_description"),
            "section_review_cases": t(lang, "section_review_cases"),
            "section_review": t(lang, "section_review"),
            "section_audience_exits": t(lang, "section_audience_exits"),
            "section_share_exits": t(lang, "section_share_exits"),
            "section_share": t(lang, "section_share"),
            "section_tokens": t(lang, "section_tokens"),
            "section_artifacts": t(lang, "section_artifacts"),
            "label_verified_support": t(lang, "label_verified_support"),
            "label_historical_platforms": t(lang, "label_historical_platforms"),
            "label_grant_count": t(lang, "label_grant_count"),
            "label_release_short": t(lang, "label_release_short"),
            "label_visibility": t(lang, "label_visibility"),
            "label_status": t(lang, "label_status"),
            "label_slug": t(lang, "label_slug"),
            "label_slug_with_hint": t(lang, "label_slug_with_hint"),
            "label_display_name": t(lang, "label_display_name"),
            "label_metadata_json": t(lang, "label_metadata_json"),
            "label_ready_at": t(lang, "label_ready_at"),
            "action_share_page": t(lang, "action_share_page"),
            "action_open_release": t(lang, "action_open_release"),
            "action_open_skill_short": t(lang, "action_open_skill_short"),
            "action_share_settings": t(lang, "action_share_settings"),
            "action_save_draft": t(lang, "action_save_draft"),
            "action_confirm_seal": t(lang, "action_confirm_seal"),
            "action_update": t(lang, "action_update"),
            "action_history": t(lang, "action_history"),
            "action_copy_command": t(lang, "action_copy_command"),
            "action_copy": t(lang, "action_copy"),
            "hint_release_immutable": t(lang, "hint_release_immutable"),
            "hint_public_review_required": t(lang, "hint_public_review_required"),
            "hint_activation_blocked": t(lang, "hint_activation_blocked"),
            "hint_activation_blocked_not_approved": t(lang, "hint_activation_blocked_not_approved"),
            "hint_activation_blocked_rejected": t(lang, "hint_activation_blocked_rejected"),
            "hint_activation_blocked_review_required": t(lang, "hint_activation_blocked_review_required"),
            "option_blocking": t(lang, "option_blocking"),
            "option_advisory": t(lang, "option_advisory"),
            "option_enabled": t(lang, "option_enabled"),
            "option_disabled": t(lang, "option_disabled"),
            "placeholder_review_note": t(lang, "placeholder_review_note"),
            "aria_review_note": t(lang, "aria_review_note"),
            "login_error": t(lang, "login_error"),
            "page_kicker_fallback": t(lang, "page_kicker_fallback"),
            "generic_unexpected_error": t(lang, "generic_unexpected_error"),
            "focus_mode_toggle": t(lang, "focus_mode_toggle"),
            "focus_mode_on": t(lang, "focus_mode_on"),
            "focus_mode_off": t(lang, "focus_mode_off"),
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
