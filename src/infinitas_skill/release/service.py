"""Thin release readiness composition layer."""

from __future__ import annotations

import json
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
from infinitas_skill.release.platform_state import (
    collect_platform_compatibility_state,
    format_blocking_platform_support,
)
from infinitas_skill.release.policy_state import (
    collect_policy_state,
    load_signing_config,
    normalize_skill_identity,
    resolve_releaser_identity,
    signer_entries,
    signing_key_path,
)
from infinitas_skill.root import ROOT

RELEASE_STATE_MODES = ("preflight", "local-preflight", "local-tag", "stable-release")


def _issue(rule_id, message, *, rule=None):
    return {
        "id": rule_id,
        "message": message,
        "rule": rule or message,
    }


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_skill(root, target):
    candidate = Path(target)
    if candidate.is_dir() and (candidate / "_meta.json").exists():
        return candidate.resolve()
    for stage in ["active", "incubating", "archived"]:
        skill_dir = Path(root) / "skills" / stage / target
        if skill_dir.is_dir() and (skill_dir / "_meta.json").exists():
            return skill_dir.resolve()
    raise ReleaseError(f"cannot resolve skill: {target}")


def expected_skill_tag(skill_dir):
    meta = load_json(Path(skill_dir) / "_meta.json")
    return meta, f"skill/{meta['name']}/v{meta['version']}"


def _review_payload(review_entries, review_evaluation):
    payload = {"reviewers": review_entries}
    if review_evaluation:
        payload.update(
            {
                "effective_review_state": review_evaluation.get("effective_review_state"),
                "required_approvals": review_evaluation.get("required_approvals"),
                "required_groups": review_evaluation.get("required_groups", []),
                "covered_groups": review_evaluation.get("covered_groups", []),
                "missing_groups": review_evaluation.get("missing_groups", []),
                "approval_count": review_evaluation.get("approval_count"),
                "blocking_rejection_count": review_evaluation.get("blocking_rejection_count"),
                "quorum_met": review_evaluation.get("quorum_met"),
                "review_gate_pass": review_evaluation.get("review_gate_pass"),
                "latest_decisions": review_evaluation.get("latest_decisions", []),
                "ignored_decisions": review_evaluation.get("ignored_decisions", []),
                "configured_groups": review_evaluation.get("configured_groups", {}),
            }
        )
    return payload


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

    issues = [_issue("namespace-policy", message) for message in policy_state["issues"]]
    warnings = list(policy_state["warnings"])
    exception_usage = []
    require_clean_worktree = mode != "local-tag"
    require_upstream_sync = mode in {"preflight", "stable-release"}
    require_fresh_platform_support = mode in {"preflight", "stable-release"}
    releaser_identity = resolve_releaser_identity(root)
    platform_compatibility = {
        "declared_support": meta.get("agent_compatible") or [],
        "verified_support": {},
        "blocking_platforms": [],
        "policy": {},
        "evaluation_error": None,
    }

    try:
        exception_policy = load_exception_policy(root)
    except ExceptionPolicyError as exc:
        raise ReleaseError("; ".join(exc.errors)) from exc

    try:
        platform_compatibility = collect_platform_compatibility_state(root, meta, identity)
    except Exception as exc:
        platform_message = f"cannot evaluate platform verified support: {exc}"
        platform_compatibility["evaluation_error"] = platform_message
        if require_fresh_platform_support and platform_compatibility.get("declared_support"):
            issues.append(
                _issue(
                    "platform-verified-support",
                    platform_message,
                    rule=(
                        "preflight and stable releases require fresh verified support "
                        "for declared platforms"
                    ),
                )
            )
        else:
            warnings.append(platform_message)
    else:
        if require_fresh_platform_support and platform_compatibility.get("blocking_platforms"):
            details = ", ".join(
                format_blocking_platform_support(item)
                for item in platform_compatibility.get("blocking_platforms", [])
            )
            issues.append(
                _issue(
                    "platform-verified-support",
                    (
                        "platform verified support is stale or missing, or the verified "
                        f"state is incompatible, for declared platforms: {details}"
                    ),
                    rule=(
                        "preflight and stable releases require fresh verified support "
                        "for declared platforms"
                    ),
                )
            )

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

    if dirty:
        if require_clean_worktree:
            issues.append(
                _issue(
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
                _issue(
                    "missing-upstream",
                    (
                        f"branch {branch or 'HEAD'} has no upstream; set one before "
                        "creating or publishing a stable release"
                    ),
                    rule="stable releases require upstream synchronization",
                )
            )
        else:
            if ahead:
                issues.append(
                    _issue(
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
                    _issue(
                        "behind-of-upstream",
                        (
                            f"branch is behind {upstream} by {behind} commit(s); update "
                            "before creating or publishing a stable release"
                        ),
                        rule="stable releases require upstream synchronization",
                    )
                )
    elif not upstream:
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

    if mode in {"local-tag", "stable-release"}:
        if not local_tag["exists"]:
            issues.append(
                _issue(
                    "missing-local-tag",
                    (
                        f"expected release tag is missing: {expected_tag}; create it "
                        f"with scripts/release-skill-tag.sh {meta['name']} --create"
                    ),
                    rule="stable releases require a signed verified local tag",
                )
            )
        else:
            if local_tag["ref_type"] != "tag":
                issues.append(
                    _issue(
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
                    _issue(
                        "unsigned-local-tag",
                        (
                            f"{expected_tag} is not signed; recreate it with "
                            f"scripts/release-skill-tag.sh {meta['name']} --create "
                            "--force"
                        ),
                        rule="stable releases require a signed verified local tag",
                    )
                )
            if not local_tag["verified"]:
                detail = local_tag["verification_error"] or "verification failed"
                issues.append(
                    _issue(
                        "unverified-local-tag",
                        (f"{expected_tag} did not verify against repo-managed signers: {detail}"),
                        rule="stable releases require a signed verified local tag",
                    )
                )
            if not local_tag["points_to_head"]:
                issues.append(
                    _issue(
                        "local-tag-not-head",
                        (
                            f"{expected_tag} does not point at HEAD; retag the current "
                            "release commit before publishing"
                        ),
                        rule="stable releases require a signed verified local tag",
                    )
                )

    if mode == "stable-release":
        if not remote_tag["query_ok"]:
            issues.append(
                _issue(
                    "remote-tag-query",
                    (
                        f"cannot verify pushed tag state on {remote_name}: "
                        f"{remote_tag['query_error']}"
                    ),
                    rule=("stable releases require remote tag verification in stable-release mode"),
                )
            )
        elif not remote_tag["tag_exists"]:
            issues.append(
                _issue(
                    "remote-tag-missing",
                    (
                        f"{expected_tag} is not pushed to {remote_name}; push it before "
                        "publishing release output"
                    ),
                    rule=("stable releases require remote tag verification in stable-release mode"),
                )
            )
        elif remote_tag["target_commit"] != head_commit:
            issues.append(
                _issue(
                    "remote-tag-mismatch",
                    (
                        f"{expected_tag} on {remote_name} points to "
                        f"{remote_tag['target_commit'] or 'an unexpected object'}, "
                        f"not HEAD {head_commit}"
                    ),
                    rule=("stable releases require remote tag verification in stable-release mode"),
                )
            )

    if mode == "preflight" and not allowed_signer_entries:
        warnings.append(
            f"{signing['allowed_signers_rel']} has no signer entries yet; signed tag "
            "verification will stay blocked until it is populated"
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
                    "for declared platforms"
                ),
                "value": {
                    "enforced": require_fresh_platform_support,
                    "declared_support": platform_compatibility.get("declared_support", []),
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
        "review": _review_payload(review_entries, review_evaluation),
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
