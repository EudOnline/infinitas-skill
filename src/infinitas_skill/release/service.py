"""Thin release readiness composition layer."""

from __future__ import annotations

from pathlib import Path

from infinitas_skill.policy.exception_policy import (
    ExceptionPolicyError,
    load_exception_policy,
    match_active_exceptions,
)
from infinitas_skill.policy.trace import build_policy_trace
from infinitas_skill.release.attestation_state import (
    collect_reproducibility_state,
    collect_transparency_log_state,
)
from infinitas_skill.release.git_state import (
    ReleaseError,
    ahead_behind,
    git,
    local_tag_state,
    remote_tag_state,
    repo_url,
    split_remote,
    tracked_upstream,
)
from infinitas_skill.release.platform_state import collect_platform_compatibility_state
from infinitas_skill.release.policy_state import (
    collect_policy_state,
    load_signing_config,
    normalize_skill_identity,
    resolve_releaser_identity,
    signer_entries,
    signing_key_path,
)
from infinitas_skill.release.release_issues import (
    apply_identity_warnings,
    apply_local_tag_findings,
    apply_platform_support_findings,
    apply_preflight_signer_warning,
    apply_remote_tag_findings,
    apply_worktree_and_upstream_findings,
    issue,
)
from infinitas_skill.release.release_resolution import (
    build_review_payload,
    expected_skill_tag,
    load_json,
    resolve_skill,
)
from infinitas_skill.root import ROOT

RELEASE_STATE_MODES = ("preflight", "local-preflight", "local-tag", "stable-release")


def collect_release_state(skill_dir, mode="stable-release", root=None):
    root = Path(root or ROOT).resolve()
    skill_dir = Path(skill_dir).resolve()
    meta, expected_tag = expected_skill_tag(skill_dir)
    identity = normalize_skill_identity(meta)
    reproducibility = collect_reproducibility_state(root, meta)
    transparency_log = collect_transparency_log_state(root, meta)
    signing = load_signing_config(root)
    head_commit = git(root, "rev-parse", "HEAD").stdout.strip()
    branch = git(root, "branch", "--show-current", check=False).stdout.strip() or None
    upstream = tracked_upstream(root)
    remote_name = split_remote(upstream, signing["default_remote"])
    ahead, behind = ahead_behind(root, upstream)
    dirty = bool(git(root, "status", "--porcelain").stdout.strip())
    allowed_signer_entries = signer_entries(signing["allowed_signers_path"])
    local_tag = local_tag_state(
        root,
        expected_tag,
        signing,
        allowed_signer_entries=allowed_signer_entries,
    )
    local_tag["points_to_head"] = bool(
        local_tag["target_commit"] and local_tag["target_commit"] == head_commit
    )
    remote_tag = remote_tag_state(root, remote_name, expected_tag)

    policy_state = collect_policy_state(skill_dir, root)
    namespace_report = policy_state["namespace_report"]
    namespace_policy_sources = policy_state["namespace_policy_sources"]
    review_entries = policy_state["review_entries"]
    review_evaluation = policy_state["review_evaluation"]

    issues = [issue("namespace-policy", message) for message in policy_state["issues"]]
    warnings = list(policy_state["warnings"])
    exception_usage = []
    require_clean_worktree = mode != "local-tag"
    require_upstream_sync = mode in {"preflight", "stable-release"}
    require_fresh_platform_support = mode in {"preflight", "stable-release"}
    releaser_identity = resolve_releaser_identity(root)
    platform_compatibility = {
        "canonical_runtime_platform": "openclaw",
        "canonical_runtime": {},
        "declared_support": meta.get("agent_compatible") or [],
        "historical_platforms": [],
        "verified_support": {},
        "blocking_platforms": [],
        "policy": {},
        "evaluation_error": None,
    }

    try:
        exception_policy = load_exception_policy(root)
    except ExceptionPolicyError as exc:
        raise ReleaseError("; ".join(exc.errors)) from exc

    platform_error: Exception | None = None
    try:
        platform_compatibility = collect_platform_compatibility_state(root, meta, identity)
    except Exception as exc:
        platform_error = exc

    apply_platform_support_findings(
        issues=issues,
        warnings=warnings,
        require_fresh_platform_support=require_fresh_platform_support,
        platform_compatibility=platform_compatibility,
        platform_error=platform_error,
    )
    apply_identity_warnings(
        warnings=warnings,
        releaser_identity=releaser_identity,
        namespace_report=namespace_report,
        identity=identity,
        transparency_log=transparency_log,
        local_tag=local_tag,
    )
    apply_worktree_and_upstream_findings(
        issues=issues,
        warnings=warnings,
        dirty=dirty,
        require_clean_worktree=require_clean_worktree,
        require_upstream_sync=require_upstream_sync,
        branch=branch,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
    )
    apply_local_tag_findings(
        issues=issues,
        mode=mode,
        local_tag=local_tag,
        expected_tag=expected_tag,
        meta_name=meta["name"],
    )
    apply_remote_tag_findings(
        issues=issues,
        mode=mode,
        remote_tag=remote_tag,
        remote_name=remote_name,
        expected_tag=expected_tag,
        head_commit=head_commit,
    )
    apply_preflight_signer_warning(
        warnings=warnings,
        mode=mode,
        allowed_signer_entries=allowed_signer_entries,
        allowed_signers_rel=signing["allowed_signers_rel"],
    )

    exception_usage = match_active_exceptions(
        "release",
        meta,
        [item["id"] for item in issues],
        root=root,
        policy=exception_policy,
    )
    waived_rule_ids = {
        matched_rule
        for item in exception_usage
        for matched_rule in item.get("matched_rules", [])
        if isinstance(matched_rule, str) and matched_rule
    }
    remaining_issues = [item for item in issues if item.get("id") not in waived_rule_ids]
    errors = [item["message"] for item in remaining_issues]

    release_trust_mode = (
        ((signing.get("config") or {}).get("attestation") or {}).get("policy") or {}
    ).get("release_trust_mode", "ssh")
    policy_trace = build_policy_trace(
        domain="release_policy",
        decision="allow" if not errors else "deny",
        summary=(
            "release readiness checks passed"
            if not errors
            else f"release readiness blocked by {len(errors)} issue(s)"
        ),
        effective_sources=list(signing.get("policy_sources", [])) + list(namespace_policy_sources),
        applied_rules=[
            {
                "id": "dirty-worktree",
                "rule": "stable releases require a clean worktree",
                "value": {"enforced": require_clean_worktree, "dirty": dirty},
            },
            {
                "id": "upstream-synchronization",
                "rule": "stable releases require upstream synchronization",
                "value": {
                    "enforced": require_upstream_sync,
                    "ahead": ahead,
                    "behind": behind,
                },
            },
            {
                "id": "platform-verified-support",
                "rule": (
                    "preflight and stable releases require fresh verified support "
                    "for the canonical OpenClaw runtime"
                ),
                "value": {
                    "enforced": require_fresh_platform_support,
                    "canonical_runtime_platform": platform_compatibility.get(
                        "canonical_runtime_platform"
                    ),
                    "canonical_runtime": platform_compatibility.get("canonical_runtime", {}),
                    "declared_support": platform_compatibility.get("declared_support", []),
                    "historical_platforms": platform_compatibility.get("historical_platforms", []),
                    "blocking_platforms": platform_compatibility.get("blocking_platforms", []),
                    "evaluation_error": platform_compatibility.get("evaluation_error"),
                },
            },
            {
                "id": "local-tag",
                "rule": "stable releases require a signed verified local tag",
                "value": expected_tag,
            },
            {
                "id": "remote-tag",
                "rule": ("stable releases require remote tag verification in stable-release mode"),
                "value": mode == "stable-release",
            },
            {
                "id": "signing-tag-format",
                "rule": "release signing config defines tag_format",
                "value": signing["tag_format"],
            },
        ],
        blocking_rules=[
            {
                "id": item["id"],
                "rule": item["rule"],
                "message": item["message"],
            }
            for item in remaining_issues
        ],
        reasons=warnings
        + [
            f"mode={mode}",
            f"release_trust_mode={release_trust_mode}",
            f"exceptions_applied={len(exception_usage)}",
        ],
        next_actions=(
            [
                "fix the blocking release errors and rerun check-release-state",
                "use --json for machine-readable policy diagnostics",
            ]
            if errors
            else ["release policy is satisfied for the current mode"]
        ),
        exceptions=exception_usage,
    )

    return {
        "mode": mode,
        "release_ready": not errors,
        "errors": errors,
        "warnings": warnings,
        "exception_usage": exception_usage,
        "policy_trace": policy_trace,
        "skill": {
            "name": meta.get("name"),
            "publisher": identity.get("publisher"),
            "qualified_name": identity.get("qualified_name"),
            "identity_mode": identity.get("identity_mode"),
            "version": meta.get("version"),
            "status": meta.get("status"),
            "path": str(skill_dir.relative_to(root)),
            "author": identity.get("author"),
            "owners": identity.get("owners", []),
            "maintainers": identity.get("maintainers", []),
        },
        "review": build_review_payload(review_entries, review_evaluation),
        "release": {
            "releaser_identity": releaser_identity,
            "namespace_policy_path": namespace_report.get("policy_path"),
            "namespace_policy_version": namespace_report.get("policy_version"),
            "transfer_required": namespace_report.get("transfer_required", False),
            "transfer_authorized": namespace_report.get("transfer_authorized", True),
            "transfer_matches": namespace_report.get("transfer_matches", []),
            "competing_claims": namespace_report.get("competing_claims", []),
            "delegated_teams": namespace_report.get("delegated_teams", {}),
            "authorized_signers": namespace_report.get("authorized_signers", []),
            "authorized_releasers": namespace_report.get("authorized_releasers", []),
            "exception_usage": exception_usage,
            "reproducibility": reproducibility,
            "transparency_log": transparency_log,
            "platform_compatibility": platform_compatibility,
        },
        "signing": {
            "tag_format": signing["tag_format"],
            "allowed_signers": signing["allowed_signers_rel"],
            "signer_count": len(allowed_signer_entries),
            "signing_key_env": signing["signing_key_env"],
            "signing_key": signing_key_path(root, signing),
        },
        "git": {
            "repo_url": repo_url(root),
            "branch": branch,
            "head_commit": head_commit,
            "upstream": upstream,
            "ahead": ahead,
            "behind": behind,
            "dirty": dirty,
            "expected_tag": expected_tag,
            "local_tag": local_tag,
            "remote_tag": remote_tag,
        },
    }


__all__ = [
    "ROOT",
    "RELEASE_STATE_MODES",
    "ReleaseError",
    "collect_platform_compatibility_state",
    "collect_release_state",
    "collect_reproducibility_state",
    "collect_transparency_log_state",
    "expected_skill_tag",
    "git",
    "load_json",
    "load_signing_config",
    "resolve_releaser_identity",
    "resolve_skill",
    "signer_entries",
    "signing_key_path",
]
