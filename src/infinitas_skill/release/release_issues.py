"""Issue and warning assembly helpers for release readiness."""

from __future__ import annotations

from typing import Any

from infinitas_skill.release.platform_state import format_blocking_platform_support


def issue(rule_id: str, message: str, *, rule: str | None = None) -> dict[str, str]:
    return {
        "id": rule_id,
        "message": message,
        "rule": rule or message,
    }


def apply_platform_support_findings(
    *,
    issues: list[dict[str, str]],
    warnings: list[str],
    require_fresh_platform_support: bool,
    platform_compatibility: dict[str, Any],
    platform_error: Exception | None = None,
) -> None:
    if platform_error is not None:
        platform_message = f"cannot evaluate platform verified support: {platform_error}"
        platform_compatibility["evaluation_error"] = platform_message
        if require_fresh_platform_support:
            issues.append(
                issue(
                    "platform-verified-support",
                    platform_message,
                    rule=(
                        "preflight and stable releases require fresh verified support "
                        "for the canonical OpenClaw runtime"
                    ),
                )
            )
        else:
            warnings.append(platform_message)
        return

    if require_fresh_platform_support and platform_compatibility.get("blocking_platforms"):
        details = ", ".join(
            format_blocking_platform_support(item)
            for item in platform_compatibility.get("blocking_platforms", [])
        )
        issues.append(
            issue(
                "platform-verified-support",
                (
                    "platform verified support is stale or missing, or the verified "
                    f"state is incompatible, for the canonical OpenClaw runtime: {details}"
                ),
                rule=(
                    "preflight and stable releases require fresh verified support "
                    "for the canonical OpenClaw runtime"
                ),
            )
        )


def apply_identity_warnings(
    *,
    warnings: list[str],
    releaser_identity: str | None,
    namespace_report: dict[str, Any],
    identity: dict[str, Any],
    transparency_log: dict[str, Any] | Any,
    local_tag: dict[str, Any],
) -> None:
    if not releaser_identity:
        warnings.append(
            "cannot determine releaser identity; set INFINITAS_SKILL_RELEASER or "
            "git config user.name/user.email"
        )
    elif namespace_report.get("authorized_releasers") and (
        releaser_identity not in namespace_report.get("authorized_releasers", [])
    ):
        warnings.append(
            f"releaser identity {releaser_identity!r} is not listed in "
            "namespace-policy authorized_releasers for "
            f"{identity.get('qualified_name') or identity.get('name')}"
        )
    if isinstance(transparency_log, dict) and transparency_log.get("error"):
        warnings.append(
            f"transparency log proof could not be verified: {transparency_log.get('error')}"
        )
    if (
        local_tag.get("signer")
        and namespace_report.get("authorized_signers")
        and (local_tag["signer"] not in namespace_report.get("authorized_signers", []))
    ):
        warnings.append(
            f"tag signer {local_tag['signer']!r} is not listed in namespace-policy "
            "authorized_signers for "
            f"{identity.get('qualified_name') or identity.get('name')}"
        )


def apply_worktree_and_upstream_findings(
    *,
    issues: list[dict[str, str]],
    warnings: list[str],
    dirty: bool,
    require_clean_worktree: bool,
    require_upstream_sync: bool,
    branch: str | None,
    upstream: str | None,
    ahead: int,
    behind: int,
) -> None:
    if dirty:
        if require_clean_worktree:
            issues.append(
                issue(
                    "dirty-worktree",
                    (
                        "worktree is dirty; commit or stash all changes before creating "
                        "or publishing a stable release"
                    ),
                    rule="stable releases require a clean worktree",
                )
            )
        else:
            warnings.append(
                "worktree is dirty; local tag release checks allow "
                "repo-managed provenance artifacts"
            )

    if require_upstream_sync:
        if not upstream:
            issues.append(
                issue(
                    "missing-upstream",
                    (
                        f"branch {branch or 'HEAD'} has no upstream; set one before "
                        "creating or publishing a stable release"
                    ),
                    rule="stable releases require upstream synchronization",
                )
            )
            return
        if ahead:
            issues.append(
                issue(
                    "ahead-of-upstream",
                    (
                        f"branch is ahead of {upstream} by {ahead} commit(s); push "
                        "before creating or publishing a stable release"
                    ),
                    rule="stable releases require upstream synchronization",
                )
            )
        if behind:
            issues.append(
                issue(
                    "behind-of-upstream",
                    (
                        f"branch is behind {upstream} by {behind} commit(s); update "
                        "before creating or publishing a stable release"
                    ),
                    rule="stable releases require upstream synchronization",
                )
            )
        return

    if not upstream:
        warnings.append(
            f"branch {branch or 'HEAD'} has no upstream; local tag release checks skip "
            "upstream synchronization"
        )
    else:
        if ahead:
            warnings.append(
                f"branch is ahead of {upstream} by {ahead} commit(s); local tag "
                "release checks allow this"
            )
        if behind:
            warnings.append(
                f"branch is behind {upstream} by {behind} commit(s); local tag "
                "release checks allow this"
            )


def apply_local_tag_findings(
    *,
    issues: list[dict[str, str]],
    mode: str,
    local_tag: dict[str, Any],
    expected_tag: str,
    meta_name: str,
) -> None:
    if mode not in {"local-tag", "stable-release"}:
        return

    if not local_tag["exists"]:
        issues.append(
            issue(
                "missing-local-tag",
                (
                    f"expected release tag is missing: {expected_tag}; create it "
                    f"with scripts/release-skill-tag.sh {meta_name} --create"
                ),
                rule="stable releases require a signed verified local tag",
            )
        )
        return

    if local_tag["ref_type"] != "tag":
        issues.append(
            issue(
                "lightweight-local-tag",
                (
                    f"{expected_tag} is a lightweight tag; stable releases "
                    "require a signed annotated tag"
                ),
                rule="stable releases require a signed verified local tag",
            )
        )
    if not local_tag["signed"]:
        issues.append(
            issue(
                "unsigned-local-tag",
                (
                    f"{expected_tag} is not signed; recreate it with "
                    f"scripts/release-skill-tag.sh {meta_name} --create "
                    "--force"
                ),
                rule="stable releases require a signed verified local tag",
            )
        )
    if not local_tag["verified"]:
        detail = local_tag["verification_error"] or "verification failed"
        issues.append(
            issue(
                "unverified-local-tag",
                f"{expected_tag} did not verify against repo-managed signers: {detail}",
                rule="stable releases require a signed verified local tag",
            )
        )
    if not local_tag["points_to_head"]:
        issues.append(
            issue(
                "local-tag-not-head",
                (
                    f"{expected_tag} does not point at HEAD; retag the current "
                    "release commit before publishing"
                ),
                rule="stable releases require a signed verified local tag",
            )
        )


def apply_remote_tag_findings(
    *,
    issues: list[dict[str, str]],
    mode: str,
    remote_tag: dict[str, Any],
    remote_name: str,
    expected_tag: str,
    head_commit: str,
) -> None:
    if mode != "stable-release":
        return
    if not remote_tag["query_ok"]:
        issues.append(
            issue(
                "remote-tag-query",
                f"cannot verify pushed tag state on {remote_name}: {remote_tag['query_error']}",
                rule="stable releases require remote tag verification in stable-release mode",
            )
        )
    elif not remote_tag["tag_exists"]:
        issues.append(
            issue(
                "remote-tag-missing",
                (
                    f"{expected_tag} is not pushed to {remote_name}; push it before "
                    "publishing release output"
                ),
                rule="stable releases require remote tag verification in stable-release mode",
            )
        )
    elif remote_tag["target_commit"] != head_commit:
        issues.append(
            issue(
                "remote-tag-mismatch",
                (
                    f"{expected_tag} on {remote_name} points to "
                    f"{remote_tag['target_commit'] or 'an unexpected object'}, "
                    f"not HEAD {head_commit}"
                ),
                rule="stable releases require remote tag verification in stable-release mode",
            )
        )


def apply_preflight_signer_warning(
    *,
    warnings: list[str],
    mode: str,
    allowed_signer_entries: list[Any],
    allowed_signers_rel: str,
) -> None:
    if mode == "preflight" and not allowed_signer_entries:
        warnings.append(
            f"{allowed_signers_rel} has no signer entries yet; signed tag "
            "verification will stay blocked until it is populated"
        )


__all__ = [
    "apply_identity_warnings",
    "apply_local_tag_findings",
    "apply_platform_support_findings",
    "apply_preflight_signer_warning",
    "apply_remote_tag_findings",
    "apply_worktree_and_upstream_findings",
    "issue",
]
