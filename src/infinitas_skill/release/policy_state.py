"""Policy and review state helpers for release readiness checks."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

from infinitas_skill.legacy import ROOT, ensure_legacy_scripts_on_path
from infinitas_skill.release.git_state import ReleaseError, git_config_value

ensure_legacy_scripts_on_path(ROOT)

exception_policy_lib = importlib.import_module("exception_policy_lib")
policy_pack_lib = importlib.import_module("policy_pack_lib")
review_lib = importlib.import_module("review_lib")
skill_identity_lib = importlib.import_module("skill_identity_lib")

ExceptionPolicyError = exception_policy_lib.ExceptionPolicyError
load_exception_policy = exception_policy_lib.load_exception_policy
match_active_exceptions = exception_policy_lib.match_active_exceptions

NamespacePolicyError = skill_identity_lib.NamespacePolicyError
load_namespace_policy = skill_identity_lib.load_namespace_policy
namespace_policy_report = skill_identity_lib.namespace_policy_report
normalize_skill_identity = skill_identity_lib.normalize_skill_identity

PolicyPackError = policy_pack_lib.PolicyPackError
load_policy_domain_resolution = policy_pack_lib.load_policy_domain_resolution

ReviewPolicyError = review_lib.ReviewPolicyError
evaluate_review_state = review_lib.evaluate_review_state
review_decision_entries = review_lib.review_decision_entries


def load_signing_config(root):
    try:
        resolution = load_policy_domain_resolution(root, "signing")
        config = resolution["effective"]
        policy_sources = resolution.get("effective_sources", [])
    except PolicyPackError as exc:
        raise ReleaseError("; ".join(exc.errors)) from exc
    tag_cfg = config.get("git_tag") or {}
    allowed_rel = (
        tag_cfg.get("allowed_signers") or config.get("allowed_signers") or "config/allowed_signers"
    )
    key_env = tag_cfg.get("signing_key_env") or "INFINITAS_SKILL_GIT_SIGNING_KEY"
    return {
        "config": config,
        "policy_sources": policy_sources,
        "tag_format": tag_cfg.get("format", "ssh"),
        "allowed_signers_rel": allowed_rel,
        "allowed_signers_path": (Path(root) / allowed_rel).resolve(),
        "default_remote": tag_cfg.get("remote", "origin"),
        "signing_key_env": key_env,
    }


def signer_entries(path):
    path_obj = Path(path)
    if not path_obj.exists():
        return []
    entries = []
    for line in path_obj.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(stripped)
    return entries


def signing_key_path(root, signing):
    env_value = os.environ.get(signing["signing_key_env"])
    if env_value:
        return env_value
    return git_config_value(root, "user.signingkey")


def resolve_releaser_identity(root):
    env_value = os.environ.get("INFINITAS_SKILL_RELEASER")
    if env_value and env_value.strip():
        return env_value.strip()
    return git_config_value(root, "user.name") or git_config_value(root, "user.email")


def _default_namespace_report():
    return {
        "policy_path": None,
        "policy_version": None,
        "authorized_signers": [],
        "authorized_releasers": [],
        "transfer_required": False,
        "transfer_authorized": True,
        "transfer_matches": [],
        "competing_claims": [],
        "warnings": [],
        "errors": [],
    }


def review_audit_entries(skill_dir):
    _reviews, review_entries = review_decision_entries(Path(skill_dir))
    entries = []
    for item in review_entries:
        reviewer = item.get("reviewer")
        decision = item.get("decision")
        if not reviewer or not decision:
            continue
        entries.append(
            {
                "reviewer": reviewer,
                "decision": decision,
                "at": item.get("at"),
                "note": item.get("note"),
                "source": item.get("source"),
                "source_kind": item.get("source_kind"),
                "source_ref": item.get("source_ref"),
                "url": item.get("url"),
            }
        )
    return entries


def collect_policy_state(skill_dir, root):
    namespace_report = _default_namespace_report()
    namespace_policy_sources = []
    issues = []
    warnings = []

    try:
        namespace_resolution = load_policy_domain_resolution(root, "namespace_policy")
        namespace_policy_sources = namespace_resolution.get("effective_sources", [])
        namespace_policy = load_namespace_policy(root)
        namespace_report = namespace_policy_report(skill_dir, root=root, policy=namespace_policy)
    except PolicyPackError as exc:
        issues.extend(exc.errors)
    except NamespacePolicyError as exc:
        issues.extend(exc.errors)
    else:
        issues.extend(namespace_report.get("errors", []))
        warnings.extend(namespace_report.get("warnings", []))

    review_entries = review_audit_entries(skill_dir)
    review_evaluation = None
    try:
        review_evaluation = evaluate_review_state(skill_dir, root=root)
    except (PolicyPackError, ReviewPolicyError) as exc:
        warnings.append(f"cannot evaluate review audit state: {'; '.join(exc.errors)}")

    return {
        "issues": issues,
        "warnings": warnings,
        "namespace_policy_sources": namespace_policy_sources,
        "namespace_report": namespace_report,
        "review_entries": review_entries,
        "review_evaluation": review_evaluation,
    }


__all__ = [
    "ExceptionPolicyError",
    "NamespacePolicyError",
    "PolicyPackError",
    "ReviewPolicyError",
    "collect_policy_state",
    "evaluate_review_state",
    "load_exception_policy",
    "load_namespace_policy",
    "load_policy_domain_resolution",
    "load_signing_config",
    "match_active_exceptions",
    "namespace_policy_report",
    "normalize_skill_identity",
    "resolve_releaser_identity",
    "review_audit_entries",
    "signer_entries",
    "signing_key_path",
]
