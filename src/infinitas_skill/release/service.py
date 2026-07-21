"""Thin release readiness composition layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    apply_identity_findings,
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

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class ReleaseStateContext:
    mode: str
    root: Path
    skill_dir: Path
    meta: JsonDict
    identity: JsonDict
    errors: list[str]
    warnings: list[str]
    exception_usage: list[JsonDict]
    policy_trace: JsonDict
    review_entries: list[JsonDict]
    review_evaluation: JsonDict | None
    releaser_identity: str | None
    namespace_report: JsonDict
    reproducibility: JsonDict
    transparency_log: JsonDict | None
    platform_compatibility: JsonDict
    signing: JsonDict
    git_state: JsonDict


def _collect_git_state(root: Path, signing: JsonDict, expected_tag: str) -> JsonDict:
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
    local_tag["is_ancestor_of_head"] = bool(
        local_tag["target_commit"]
        and git(
            root,
            "merge-base",
            "--is-ancestor",
            str(local_tag["target_commit"]),
            head_commit,
            check=False,
        ).returncode
        == 0
    )
    remote_tag = remote_tag_state(root, remote_name, expected_tag)
    return {
        "repo_url": repo_url(root),
        "branch": branch,
        "head_commit": head_commit,
        "upstream": upstream,
        "remote_name": remote_name,
        "ahead": ahead,
        "behind": behind,
        "dirty": dirty,
        "expected_tag": expected_tag,
        "local_tag": local_tag,
        "remote_tag": remote_tag,
        "allowed_signer_entries": allowed_signer_entries,
    }


def _collect_platform_state(
    root: Path, meta: JsonDict, identity: JsonDict
) -> tuple[JsonDict, Exception | None]:
    state: dict[str, Any] = {
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
        return collect_platform_compatibility_state(root, meta, identity), None
    except Exception as exc:
        return state, exc


def _apply_release_findings(
    *,
    issues: list[JsonDict],
    warnings: list[str],
    mode: str,
    meta: JsonDict,
    identity: JsonDict,
    expected_tag: str,
    signing: JsonDict,
    git_state: JsonDict,
    namespace_report: JsonDict,
    transparency_log: JsonDict | None,
    platform_compatibility: JsonDict,
    reproducibility: JsonDict,
    platform_error: Exception | None,
    releaser_identity: str | None,
) -> tuple[bool, bool, bool]:
    require_clean_worktree = mode != "local-tag"
    require_upstream_sync = mode in {"preflight", "stable-release"}
    require_fresh_platform_support = mode in {"preflight", "stable-release"}
    apply_platform_support_findings(
        issues=issues,
        warnings=warnings,
        require_fresh_platform_support=require_fresh_platform_support,
        platform_compatibility=platform_compatibility,
        platform_error=platform_error,
    )
    apply_identity_findings(
        issues=issues,
        warnings=warnings,
        mode=mode,
        releaser_identity=releaser_identity,
        namespace_report=namespace_report,
        identity=identity,
        transparency_log=transparency_log,
        local_tag=git_state["local_tag"],
    )
    apply_worktree_and_upstream_findings(
        issues=issues,
        warnings=warnings,
        dirty=git_state["dirty"],
        require_clean_worktree=require_clean_worktree,
        require_upstream_sync=require_upstream_sync,
        branch=git_state["branch"],
        upstream=git_state["upstream"],
        ahead=git_state["ahead"],
        behind=git_state["behind"],
    )
    apply_local_tag_findings(
        issues=issues,
        mode=mode,
        local_tag=git_state["local_tag"],
        expected_tag=expected_tag,
        meta_name=meta["name"],
        reproducibility=reproducibility,
    )
    apply_remote_tag_findings(
        issues=issues,
        mode=mode,
        remote_tag=git_state["remote_tag"],
        remote_name=git_state["remote_name"],
        expected_tag=expected_tag,
        head_commit=git_state["head_commit"],
        reproducibility=reproducibility,
    )
    apply_preflight_signer_warning(
        warnings=warnings,
        mode=mode,
        allowed_signer_entries=git_state["allowed_signer_entries"],
        allowed_signers_rel=signing["allowed_signers_rel"],
    )
    return require_clean_worktree, require_upstream_sync, require_fresh_platform_support


def _apply_release_exceptions(
    meta: JsonDict, issues: list[JsonDict], root: Path, exception_policy: JsonDict
) -> tuple[list[JsonDict], list[JsonDict]]:
    usage = match_active_exceptions(
        "release",
        meta,
        [item["id"] for item in issues],
        root=root,
        policy=exception_policy,
    )
    waived = {
        rule_id
        for item in usage
        for rule_id in item.get("matched_rules", [])
        if isinstance(rule_id, str) and rule_id
    }
    remaining = [item for item in issues if item.get("id") not in waived]
    return usage, remaining


def _release_policy_trace(
    *,
    mode: str,
    errors: list[str],
    warnings: list[str],
    remaining_issues: list[JsonDict],
    exception_usage: list[JsonDict],
    signing: JsonDict,
    namespace_policy_sources: list[JsonDict],
    expected_tag: str,
    git_state: JsonDict,
    platform_compatibility: JsonDict,
    enforcement: tuple[bool, bool, bool],
) -> JsonDict:
    require_clean_worktree, require_upstream_sync, require_fresh_platform_support = enforcement
    trust_mode = (((signing.get("config") or {}).get("attestation") or {}).get("policy") or {}).get(
        "release_trust_mode", "ssh"
    )
    return build_policy_trace(
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
                "value": {"enforced": require_clean_worktree, "dirty": git_state["dirty"]},
            },
            {
                "id": "upstream-synchronization",
                "rule": "stable releases require upstream synchronization",
                "value": {
                    "enforced": require_upstream_sync,
                    "ahead": git_state["ahead"],
                    "behind": git_state["behind"],
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
                "rule": "stable releases require remote tag verification in stable-release mode",
                "value": mode == "stable-release",
            },
            {
                "id": "signing-tag-format",
                "rule": "release signing config defines tag_format",
                "value": signing["tag_format"],
            },
        ],
        blocking_rules=[
            {"id": item["id"], "rule": item["rule"], "message": item["message"]}
            for item in remaining_issues
        ],
        reasons=warnings
        + [
            f"mode={mode}",
            f"release_trust_mode={trust_mode}",
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


def _release_state_payload(context: ReleaseStateContext) -> JsonDict:
    mode = context.mode
    meta = context.meta
    identity = context.identity
    namespace_report = context.namespace_report
    signing = context.signing
    git_state = context.git_state
    return {
        "mode": mode,
        "release_ready": not context.errors,
        "errors": context.errors,
        "warnings": context.warnings,
        "exception_usage": context.exception_usage,
        "policy_trace": context.policy_trace,
        "skill": {
            "name": meta.get("name"),
            "publisher": identity.get("publisher"),
            "qualified_name": identity.get("qualified_name"),
            "identity_mode": identity.get("identity_mode"),
            "version": meta.get("version"),
            "status": meta.get("status"),
            "path": str(context.skill_dir.relative_to(context.root)),
            "author": identity.get("author"),
            "owners": identity.get("owners", []),
            "maintainers": identity.get("maintainers", []),
        },
        "review": build_review_payload(context.review_entries, context.review_evaluation),
        "release": {
            "releaser_identity": context.releaser_identity,
            "namespace_policy_path": namespace_report.get("policy_path"),
            "namespace_policy_version": namespace_report.get("policy_version"),
            "transfer_required": namespace_report.get("transfer_required", False),
            "transfer_authorized": namespace_report.get("transfer_authorized", True),
            "transfer_matches": namespace_report.get("transfer_matches", []),
            "competing_claims": namespace_report.get("competing_claims", []),
            "delegated_teams": namespace_report.get("delegated_teams", {}),
            "authorized_signers": namespace_report.get("authorized_signers", []),
            "authorized_releasers": namespace_report.get("authorized_releasers", []),
            "exception_usage": context.exception_usage,
            "reproducibility": context.reproducibility,
            "transparency_log": context.transparency_log,
            "platform_compatibility": context.platform_compatibility,
        },
        "signing": {
            "tag_format": signing["tag_format"],
            "allowed_signers": signing["allowed_signers_rel"],
            "signer_count": len(git_state["allowed_signer_entries"]),
            "signing_key_env": signing["signing_key_env"],
            "signing_key": signing_key_path(context.root, signing),
        },
        "git": {
            key: value
            for key, value in git_state.items()
            if key not in {"remote_name", "allowed_signer_entries"}
        },
    }


def collect_release_state(
    skill_dir: str | Path,
    mode: str = "stable-release",
    root: str | Path | None = None,
    releaser: str | None = None,
) -> JsonDict:
    root = Path(root or ROOT).resolve()
    skill_dir = Path(skill_dir).resolve()
    meta, expected_tag = expected_skill_tag(skill_dir)
    identity = normalize_skill_identity(meta)
    reproducibility = collect_reproducibility_state(root, meta)
    transparency_log = collect_transparency_log_state(root, meta)
    signing = load_signing_config(root)
    git_state = _collect_git_state(root, signing, expected_tag)

    policy_state = collect_policy_state(skill_dir, root)
    namespace_report = policy_state["namespace_report"]
    namespace_policy_sources = policy_state["namespace_policy_sources"]
    review_entries = policy_state["review_entries"]
    review_evaluation = policy_state["review_evaluation"]

    issues = [issue("namespace-policy", message) for message in policy_state["issues"]]
    warnings = list(policy_state["warnings"])
    releaser_identity = releaser or resolve_releaser_identity(root)
    try:
        exception_policy = load_exception_policy(root)
    except ExceptionPolicyError as exc:
        raise ReleaseError("; ".join(exc.errors)) from exc
    platform_compatibility, platform_error = _collect_platform_state(root, meta, identity)
    enforcement = _apply_release_findings(
        issues=issues,
        warnings=warnings,
        mode=mode,
        meta=meta,
        identity=identity,
        expected_tag=expected_tag,
        signing=signing,
        git_state=git_state,
        namespace_report=namespace_report,
        transparency_log=transparency_log,
        platform_compatibility=platform_compatibility,
        reproducibility=reproducibility,
        platform_error=platform_error,
        releaser_identity=releaser_identity,
    )
    exception_usage, remaining_issues = _apply_release_exceptions(
        meta, issues, root, exception_policy
    )
    errors = [item["message"] for item in remaining_issues]
    policy_trace = _release_policy_trace(
        mode=mode,
        errors=errors,
        warnings=warnings,
        remaining_issues=remaining_issues,
        exception_usage=exception_usage,
        signing=signing,
        namespace_policy_sources=namespace_policy_sources,
        expected_tag=expected_tag,
        git_state=git_state,
        platform_compatibility=platform_compatibility,
        enforcement=enforcement,
    )

    return _release_state_payload(
        ReleaseStateContext(
            mode=mode,
            root=root,
            skill_dir=skill_dir,
            meta=meta,
            identity=identity,
            errors=errors,
            warnings=warnings,
            exception_usage=exception_usage,
            policy_trace=policy_trace,
            review_entries=review_entries,
            review_evaluation=review_evaluation,
            releaser_identity=releaser_identity,
            namespace_report=namespace_report,
            reproducibility=reproducibility,
            transparency_log=transparency_log,
            platform_compatibility=platform_compatibility,
            signing=signing,
            git_state=git_state,
        )
    )


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
