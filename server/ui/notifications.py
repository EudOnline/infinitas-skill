from __future__ import annotations

from typing import Any

from server.ui.formatting import humanize_status, humanize_timestamp
from server.ui.i18n import pick_lang


def describe_skills_page(
    lang: str,
    *,
    skills_count: int,
    drafts_count: int,
    releases_count: int,
    exposures_count: int,
    total_access_count: int,
    review_cases_count: int,
) -> dict[str, Any]:
    return {
        "title": pick_lang(lang, "技能生命周期", "Skill lifecycle"),
        "content": pick_lang(
            lang,
            (
                "用新的领域语言查看技能、草稿、发布、分享和审核状态，"
                "所有流转都收拢到同一套 private-first 生命周期里。"
            ),
            (
                "Track skills, drafts, releases, sharing, and review "
                "with one private-first lifecycle vocabulary."
            ),
        ),
        "cli_command": (
            "python scripts/registryctl.py --base-url https://skills.example.com "
            "--token <token> skills get <skill-id>"
        ),
        "stats": [
            {
                "value": str(skills_count),
                "label": pick_lang(lang, "技能", "Skills"),
                "detail": pick_lang(lang, "当前可见技能", "Visible skills"),
            },
            {
                "value": str(drafts_count),
                "label": pick_lang(lang, "草稿", "Drafts"),
                "detail": pick_lang(lang, "可继续编辑", "Still editable"),
            },
            {
                "value": str(releases_count),
                "label": pick_lang(lang, "发布", "Releases"),
                "detail": pick_lang(lang, "已生成 release", "Materialized releases"),
            },
            {
                "value": str(exposures_count),
                "label": pick_lang(lang, "分享", "Share"),
                "detail": pick_lang(lang, "暴露策略", "Exposure policies"),
            },
            {
                "value": str(total_access_count),
                "label": pick_lang(lang, "访问", "Access"),
                "detail": pick_lang(lang, "令牌与授权", "Tokens and grants"),
            },
            {
                "value": str(review_cases_count),
                "label": pick_lang(lang, "审核", "Review"),
                "detail": pick_lang(lang, "公开流转审核单", "Review cases for exposure"),
            },
        ],
    }


def describe_skill_detail_page(
    lang: str,
    *,
    skill: object,
    principal_name: str,
    draft_count: int,
    release_count: int,
) -> dict[str, Any]:
    return {
        "title": skill.display_name,
        "content": pick_lang(
            lang,
            "这是技能命名空间下的单个技能视图，可直接追踪草稿、版本和发布状态。",
            "This skill detail view tracks drafts, versions, and releases inside one namespace.",
        ),
        "cli_command": (
            "python scripts/registryctl.py --base-url https://skills.example.com "
            f"--token <token> skills get {skill.id}"
        ),
        "stats": [
            {
                "value": principal_name,
                "label": pick_lang(lang, "命名空间", "Namespace"),
                "detail": skill.slug,
            },
            {
                "value": str(draft_count),
                "label": pick_lang(lang, "草稿", "Drafts"),
                "detail": pick_lang(lang, "当前技能草稿", "Open drafts"),
            },
            {
                "value": str(release_count),
                "label": pick_lang(lang, "发布", "Releases"),
                "detail": pick_lang(lang, "关联 release", "Linked releases"),
            },
        ],
    }


def describe_draft_detail_page(
    lang: str,
    *,
    draft: object,
    base_version: object | None,
    skill_name: str,
) -> dict[str, Any]:
    return {
        "title": pick_lang(lang, "草稿详情", "Draft detail"),
        "content": pick_lang(
            lang,
            "草稿是可编辑工作区。这里展示内容引用、元数据快照以及后续封版关系。",
            (
                "Drafts are editable workspaces. This view shows content refs, "
                "metadata snapshots, and the later sealed lineage."
            ),
        ),
        "cli_command": (
            "python scripts/registryctl.py --base-url https://skills.example.com "
            f"--token <token> drafts update {draft.id} --metadata-json '{{}}'"
        ),
        "stats": [
            {
                "value": humanize_status(draft.state, lang),
                "label": pick_lang(lang, "状态", "State"),
                "detail": pick_lang(lang, "草稿当前状态", "Current draft state"),
            },
            {
                "value": base_version.version if base_version else "-",
                "label": pick_lang(lang, "基线版本", "Base version"),
                "detail": pick_lang(lang, "可为空", "Optional"),
            },
            {
                "value": humanize_timestamp(draft.updated_at.isoformat()),
                "label": pick_lang(lang, "更新时间", "Updated"),
                "detail": skill_name,
            },
        ],
    }


def describe_release_detail_page(
    lang: str,
    *,
    release: object,
    version: object,
    skill_name: str,
    artifacts_count: int,
    exposures_count: int,
) -> dict[str, Any]:
    return {
        "title": pick_lang(lang, "发布详情", "Release detail"),
        "content": pick_lang(
            lang,
            "发布是不可变交付物。这里把产物、可见性和后续分享策略集中在一起。",
            (
                "A release is the immutable delivery unit. This page groups artifacts, "
                "visibility, and downstream sharing state together."
            ),
        ),
        "cli_command": (
            "python scripts/registryctl.py --base-url https://skills.example.com "
            f"--token <token> releases get {release.id}"
        ),
        "stats": [
            {
                "value": skill_name,
                "label": pick_lang(lang, "技能", "Skill"),
                "detail": version.version,
            },
            {
                "value": humanize_status(release.state, lang),
                "label": pick_lang(lang, "状态", "State"),
                "detail": pick_lang(lang, "release 生命周期", "Release lifecycle"),
            },
            {
                "value": str(artifacts_count),
                "label": pick_lang(lang, "产物", "Artifacts"),
                "detail": pick_lang(
                    lang, "manifest / bundle / signature", "manifest / bundle / signature"
                ),
            },
            {
                "value": str(exposures_count),
                "label": pick_lang(lang, "分享", "Share"),
                "detail": pick_lang(lang, "可见性出口", "Audience exits"),
            },
        ],
    }


def describe_release_share_page(
    lang: str,
    *,
    release: object,
    version: object,
    skill_name: str,
    exposures: list[object],
) -> dict[str, Any]:
    return {
        "title": pick_lang(lang, "分享与可见性", "Share and visibility"),
        "content": pick_lang(
            lang,
            (
                "一个 release 可以同时拥有私人、令牌共享和公开三种出口。"
                "公开出口必须经过审核，私人出口可直接启用。"
            ),
            (
                "A release can expose private, token-shared, "
                "and public audiences at the same time. "
                "Public audiences must pass review while private ones can activate directly."
            ),
        ),
        "cli_command": (
            "python scripts/registryctl.py --base-url https://skills.example.com "
            f"--token <token> exposures create {release.id} --audience-type public"
        ),
        "stats": [
            {
                "value": skill_name,
                "label": pick_lang(lang, "技能", "Skill"),
                "detail": version.version,
            },
            {
                "value": str(sum(1 for item in exposures if item.audience_type == "private")),
                "label": pick_lang(lang, "私人", "Private"),
                "detail": pick_lang(lang, "仅作者侧", "Author-side only"),
            },
            {
                "value": str(sum(1 for item in exposures if item.audience_type == "grant")),
                "label": pick_lang(lang, "令牌共享", "Shared by token"),
                "detail": pick_lang(lang, "细到 token", "Token-scoped access"),
            },
            {
                "value": str(sum(1 for item in exposures if item.audience_type == "public")),
                "label": pick_lang(lang, "公开", "Public"),
                "detail": pick_lang(lang, "匿名可见", "Anonymous install path"),
            },
        ],
    }


def describe_access_tokens_page(
    lang: str,
    *,
    credentials: list[object],
    grants: list[object],
) -> dict[str, Any]:
    return {
        "title": pick_lang(lang, "访问令牌与授权", "Access tokens and grants"),
        "content": pick_lang(
            lang,
            (
                "这里同时展示个人 token 和 grant 绑定令牌。后续要做更细粒度权限，"
                "只需要在 grant / credential 层扩展，不必再改技能生命周期。"
            ),
            (
                "This page groups personal tokens and grant-bound credentials. "
                "Finer permission models can grow inside grants and credentials "
                "without reshaping the skill lifecycle."
            ),
        ),
        "cli_command": (
            "python scripts/registryctl.py --base-url https://skills.example.com "
            "--token <token> tokens me"
        ),
        "stats": [
            {
                "value": str(len(credentials)),
                "label": pick_lang(lang, "令牌", "Tokens"),
                "detail": pick_lang(lang, "当前可见 credential", "Visible credentials"),
            },
            {
                "value": str(sum(1 for item in credentials if item.type == "personal_token")),
                "label": pick_lang(lang, "个人", "Personal"),
                "detail": pick_lang(lang, "用户会话 token", "User session tokens"),
            },
            {
                "value": str(sum(1 for item in credentials if item.type == "grant_token")),
                "label": pick_lang(lang, "授权", "Grant"),
                "detail": pick_lang(lang, "共享 / 安装 token", "Shared install tokens"),
            },
            {
                "value": str(len(grants)),
                "label": pick_lang(lang, "授权记录", "Grant records"),
                "detail": pick_lang(lang, "与 exposure 绑定", "Bound to exposures"),
            },
        ],
    }


def describe_review_cases_page(lang: str, *, review_cases: list[object]) -> dict[str, Any]:
    return {
        "title": pick_lang(lang, "审核收件箱", "Review inbox"),
        "content": pick_lang(
            lang,
            "公开技能必须经过审核。这个收件箱把公开 exposure 的审核需求和当前结论统一放在一起。",
            (
                "Public skills must pass review. This inbox gathers review needs "
                "and current outcomes for public-facing exposures."
            ),
        ),
        "cli_command": (
            "python scripts/registryctl.py --base-url https://skills.example.com "
            "--token <token> reviews get-case <review-case-id>"
        ),
        "stats": [
            {
                "value": str(len(review_cases)),
                "label": pick_lang(lang, "总数", "Total"),
                "detail": pick_lang(lang, "当前可见 case", "Visible review cases"),
            },
            {
                "value": str(sum(1 for item in review_cases if item.state == "open")),
                "label": pick_lang(lang, "待处理", "Open"),
                "detail": pick_lang(lang, "仍待结论", "Still awaiting a decision"),
            },
            {
                "value": str(sum(1 for item in review_cases if item.state == "approved")),
                "label": pick_lang(lang, "已通过", "Approved"),
                "detail": pick_lang(lang, "可以公开", "Ready for public install"),
            },
            {
                "value": str(sum(1 for item in review_cases if item.state == "rejected")),
                "label": pick_lang(lang, "已拒绝", "Rejected"),
                "detail": pick_lang(lang, "需要回退策略", "Needs a fallback audience"),
            },
        ],
    }


__all__ = [
    "describe_access_tokens_page",
    "describe_draft_detail_page",
    "describe_release_detail_page",
    "describe_release_share_page",
    "describe_review_cases_page",
    "describe_skill_detail_page",
    "describe_skills_page",
]
