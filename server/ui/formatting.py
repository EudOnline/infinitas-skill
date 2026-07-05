from __future__ import annotations

import json
from datetime import datetime

from fastapi import Request

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
        {},
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
        {},
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
        "session_ui": {},
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
            "skills_section_title": t(lang, "skills_section_title"),
            "skills_section_subtitle": t(lang, "skills_section_subtitle"),
            "copy_inspect_action": t(lang, "copy_inspect_action"),
            "auth_modal_title": t(lang, "auth_modal_title"),
            "console_auth_modal_title": t(lang, "console_auth_modal_title"),
            "auth_verify_loading": t(lang, "auth_verify_loading"),
            "auth_login": t(lang, "auth_login"),
            "auth_enter_username": t(lang, "auth_enter_username"),
            "auth_enter_password": t(lang, "auth_enter_password"),
            "auth_username_min": t(lang, "auth_username_min"),
            "auth_password_min": t(lang, "auth_password_min"),
            "auth_username_max": t(lang, "auth_username_max"),
            "auth_password_max": t(lang, "auth_password_max"),
            "auth_invalid_credentials": t(lang, "auth_invalid_credentials"),
            "auth_verify_failed": t(lang, "auth_verify_failed"),
            "auth_network_error": t(lang, "auth_network_error"),
            "auth_bad_server_data": t(lang, "auth_bad_server_data"),
            "auth_session_active": t(lang, "auth_session_active"),
            "show_password": t(lang, "show_password"),
            "hide_password": t(lang, "hide_password"),
            "toggle_password_visibility": t(lang, "toggle_password_visibility"),
            "user_panel_theme_light": t(lang, "user_panel_theme_light"),
            "user_panel_theme_dark": t(lang, "user_panel_theme_dark"),
            "user_menu_anon_label": t(lang, "user_menu_anon_label"),
            "user_menu_logged_label": t(lang, "user_menu_logged_label"),
            "console_session_guest": t(lang, "console_session_guest"),
            "console_session_ready": t(lang, "console_session_ready"),
            "role_maintainer": t(lang, "role_maintainer"),
            "role_contributor": t(lang, "role_contributor"),
            "theme_light_name": t(lang, "theme_light_name"),
            "theme_dark_name": t(lang, "theme_dark_name"),
            "generic_action_failed": t(lang, "generic_action_failed"),
            "loading": t(lang, "loading"),
            "skill_created": t(lang, "skill_created"),
            "skill_create_error": t(lang, "skill_create_error"),
            "invalid_json": t(lang, "invalid_json"),
            "version_created": t(lang, "version_created"),
            "version_create_error": t(lang, "version_create_error"),
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
            "review_requirement_blocking": t(lang, "review_requirement_blocking"),
            "review_requirement_none": t(lang, "review_requirement_none"),
            "label_state": t(lang, "label_state"),
            "label_artifacts": t(lang, "label_artifacts"),
            "search_install_publisher": t(lang, "search_install_publisher"),
            "search_install_install_scope": t(lang, "search_install_install_scope"),
            "search_install_listing_mode": t(lang, "search_install_listing_mode"),
            "search_install_runtime": t(lang, "search_install_runtime"),
            "search_install_readiness": t(lang, "search_install_readiness"),
            "search_install_workspace_targets": t(lang, "search_install_workspace_targets"),
            "search_install_bundle_sha256": t(lang, "search_install_bundle_sha256"),
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
            "table_col_type": t(lang, "table_col_type"),
            "table_col_kind": t(lang, "table_col_kind"),
            "table_col_release": t(lang, "table_col_release"),
            "table_col_state": t(lang, "table_col_state"),
            "table_col_size": t(lang, "table_col_size"),
            "table_col_storage_uri": t(lang, "table_col_storage_uri"),
            "table_col_listing": t(lang, "table_col_listing"),
            "table_col_actions": t(lang, "table_col_actions"),
            "table_col_install": t(lang, "table_col_install"),
            "table_col_version": t(lang, "table_col_version"),
            "table_col_created": t(lang, "table_col_created"),
            "section_releases": t(lang, "section_releases"),
            "option_public": t(lang, "option_public"),
            "option_private": t(lang, "option_private"),
            "option_authenticated": t(lang, "option_authenticated"),
            "option_grant": t(lang, "option_grant"),
            "action_edit": t(lang, "action_edit"),
            "badge_access_denied": t(lang, "badge_access_denied"),
            "option_listed": t(lang, "option_listed"),
            "option_direct_only": t(lang, "option_direct_only"),
            "option_install_enabled": t(lang, "option_install_enabled"),
            "option_install_disabled": t(lang, "option_install_disabled"),
            "option_no_review": t(lang, "option_no_review"),
            "label_review_mode": t(lang, "label_review_mode"),
            "login_badge": t(lang, "login_badge"),
            "login_title": t(lang, "login_title"),
            "login_desc": t(lang, "login_desc"),
            "login_input_label": t(lang, "login_input_label"),
            "login_password_label": t(lang, "login_password_label"),
            "login_placeholder": t(lang, "login_placeholder"),
            "login_password_placeholder": t(lang, "login_password_placeholder"),
            "login_aria_label": t(lang, "login_aria_label"),
            "toggle_password_title": t(lang, "toggle_password_title"),
            "login_hint": t(lang, "login_hint"),
            "login_button": t(lang, "login_button"),
            "empty_releases": t(lang, "empty_releases"),
            "empty_tokens": t(lang, "empty_tokens"),
            "empty_artifacts": t(lang, "empty_artifacts"),
            "action_activate": t(lang, "action_activate"),
            "action_revoke": t(lang, "action_revoke"),
            "aria_main_content": t(lang, "aria_main_content"),
            "aria_primary_navigation": t(lang, "aria_primary_navigation"),
            "search_aria_label": t(lang, "search_aria_label"),
            "skip_to_main_content": t(lang, "skip_to_main_content"),
            "meta_description": t(lang, "meta_description"),
            "section_tokens": t(lang, "section_tokens"),
            "section_artifacts": t(lang, "section_artifacts"),
            "label_visibility": t(lang, "label_visibility"),
            "label_slug": t(lang, "label_slug"),
            "action_update": t(lang, "action_update"),
            "action_copy": t(lang, "action_copy"),
            "hint_public_review_required": t(lang, "hint_public_review_required"),
            "hint_activation_blocked": t(lang, "hint_activation_blocked"),
            "hint_activation_blocked_not_approved": t(lang, "hint_activation_blocked_not_approved"),
            "hint_activation_blocked_rejected": t(lang, "hint_activation_blocked_rejected"),
            "hint_activation_blocked_review_required": t(
                lang, "hint_activation_blocked_review_required"
            ),
            "option_blocking": t(lang, "option_blocking"),
            "option_advisory": t(lang, "option_advisory"),
            "login_error": t(lang, "login_error"),
            "page_kicker_fallback": t(lang, "page_kicker_fallback"),
            "focus_mode_toggle": t(lang, "focus_mode_toggle"),
            "action_back_to_library": t(lang, "action_back_to_library"),
            "action_back_to_object": t(lang, "action_back_to_object"),
            "action_create_share_link": t(lang, "action_create_share_link"),
            "action_create_visibility": t(lang, "action_create_visibility"),
            "action_inspect_access": t(lang, "action_inspect_access"),
            "action_issue_token": t(lang, "action_issue_token"),
            "action_open_access": t(lang, "action_open_access"),
            "action_open_activity": t(lang, "action_open_activity"),
            "action_open_library": t(lang, "action_open_library"),
            "action_open_object": t(lang, "action_open_object"),
            "action_open_shares": t(lang, "action_open_shares"),
            "action_shares": t(lang, "action_shares"),
            "action_working": t(lang, "action_working"),
            "aria_filter_event": t(lang, "aria_filter_event"),
            "aria_filter_kind": t(lang, "aria_filter_kind"),
            "aria_object_tabs": t(lang, "aria_object_tabs"),
            "aria_search_objects": t(lang, "aria_search_objects"),
            "auth_cancel": t(lang, "auth_cancel"),
            "auth_close": t(lang, "auth_close"),
            "auth_invalid": t(lang, "auth_invalid"),
            "auth_modal_desc": t(lang, "auth_modal_desc"),
            "auth_modal_hint": t(lang, "auth_modal_hint"),
            "auth_modal_username_placeholder": t(lang, "auth_modal_username_placeholder"),
            "auth_modal_password_placeholder": t(lang, "auth_modal_password_placeholder"),
            "auth_verify": t(lang, "auth_verify"),
            "cli_mirror_label": t(lang, "cli_mirror_label"),
            "console_section_title": t(lang, "console_section_title"),
            "console_session_desc": t(lang, "console_session_desc"),
            "console_session_label": t(lang, "console_session_label"),
            "console_session_open_auth": t(lang, "console_session_open_auth"),
            "copy_button_label": t(lang, "copy_button_label"),
            "copy_share_id": t(lang, "copy_share_id"),
            "copy_token_id": t(lang, "copy_token_id"),
            "empty_activity_desc": t(lang, "empty_activity_desc"),
            "empty_library_desc": t(lang, "empty_library_desc"),
            "empty_search_desc": t(lang, "empty_search_desc"),
            "empty_share_links": t(lang, "empty_share_links"),
            "empty_share_links_hint": t(lang, "empty_share_links_hint"),
            "empty_token_activity": t(lang, "empty_token_activity"),
            "empty_tokens_hint": t(lang, "empty_tokens_hint"),
            "empty_visibility_channels": t(lang, "empty_visibility_channels"),
            "filter_all": t(lang, "filter_all"),
            "filter_aria_label": t(lang, "filter_aria_label"),
            "filter_placeholder": t(lang, "filter_placeholder"),
            "filter_share": t(lang, "filter_share"),
            "filter_skills": t(lang, "filter_skills"),
            "filter_token": t(lang, "filter_token"),
            "filter_visibility": t(lang, "filter_visibility"),
            "heading_admin_token": t(lang, "heading_admin_token"),
            "heading_properties": t(lang, "heading_properties"),
            "heading_reference": t(lang, "heading_reference"),
            "heading_registry_scope": t(lang, "heading_registry_scope"),
            "hint_grant_visibility_required": t(lang, "hint_grant_visibility_required"),
            "label_actor": t(lang, "label_actor"),
            "label_admin_env": t(lang, "label_admin_env"),
            "label_agent_name": t(lang, "label_agent_name"),
            "label_agent_tokens": t(lang, "label_agent_tokens"),
            "label_bootstrap_admins": t(lang, "label_bootstrap_admins"),
            "label_kind": t(lang, "label_kind"),
            "label_object": t(lang, "label_object"),
            "label_object_types": t(lang, "label_object_types"),
            "label_read_tokens": t(lang, "label_read_tokens"),
            "label_releases": t(lang, "label_releases"),
            "label_share_links": t(lang, "label_share_links"),
            "label_share_name": t(lang, "label_share_name"),
            "label_tokens": t(lang, "label_tokens"),
            "label_updated": t(lang, "label_updated"),
            "page_access_title": t(lang, "page_access_title"),
            "page_activity_title": t(lang, "page_activity_title"),
            "page_settings_title": t(lang, "page_settings_title"),
            "page_shares_title": t(lang, "page_shares_title"),
            "placeholder_agent_label": t(lang, "placeholder_agent_label"),
            "placeholder_search_objects": t(lang, "placeholder_search_objects"),
            "placeholder_share_label": t(lang, "placeholder_share_label"),
            "placeholder_share_password": t(lang, "placeholder_share_password"),
            "quick_start_hint": t(lang, "quick_start_hint"),
            "quick_start_title": t(lang, "quick_start_title"),
            "safety_note_1": t(lang, "safety_note_1"),
            "search_install_panel_label": t(lang, "search_install_panel_label"),
            "search_shortcut_hint": t(lang, "search_shortcut_hint"),
            "section_create_share_link": t(lang, "section_create_share_link"),
            "section_issue_agent_token": t(lang, "section_issue_agent_token"),
            "section_manage_visibility": t(lang, "section_manage_visibility"),
            "section_share_links": t(lang, "section_share_links"),
            "section_token_activity": t(lang, "section_token_activity"),
            "section_visibility_channels": t(lang, "section_visibility_channels"),
            "settings_label": t(lang, "settings_label"),
            "share_create_error": t(lang, "share_create_error"),
            "share_created": t(lang, "share_created"),
            "share_revoke_error": t(lang, "share_revoke_error"),
            "tab_access": t(lang, "tab_access"),
            "tab_overview": t(lang, "tab_overview"),
            "tab_releases": t(lang, "tab_releases"),
            "tab_shares": t(lang, "tab_shares"),
            "table_col_detail": t(lang, "table_col_detail"),
            "table_col_event": t(lang, "table_col_event"),
            "table_col_expiry": t(lang, "table_col_expiry"),
            "table_col_object": t(lang, "table_col_object"),
            "table_col_password": t(lang, "table_col_password"),
            "table_col_readiness": t(lang, "table_col_readiness"),
            "table_col_timestamp": t(lang, "table_col_timestamp"),
            "table_col_token": t(lang, "table_col_token"),
            "table_col_usage": t(lang, "table_col_usage"),
            "table_col_visibility": t(lang, "table_col_visibility"),
            "text_no_summary": t(lang, "text_no_summary"),
            "title_library": t(lang, "title_library"),
            "token_create_error": t(lang, "token_create_error"),
            "token_created": t(lang, "token_created"),
            "token_revoke_error": t(lang, "token_revoke_error"),
            "token_type_publisher": t(lang, "token_type_publisher"),
            "token_type_reader": t(lang, "token_type_reader"),
            "user_panel_auth_action": t(lang, "user_panel_auth_action"),
            "user_panel_auth_desc": t(lang, "user_panel_auth_desc"),
            "user_panel_auth_title": t(lang, "user_panel_auth_title"),
            "user_panel_background_label": t(lang, "user_panel_background_label"),
            "user_panel_logout": t(lang, "user_panel_logout"),
            "back_home": t(lang, "back_home"),
        },
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
