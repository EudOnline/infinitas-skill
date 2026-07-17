"""Provenance document construction for the release materializer.

Builds the full provenance JSON payload including git context, source
snapshot, registry payload, dependency steps, review, release, and
attestation sections.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from infinitas_skill.release.policy_state import resolve_releaser_identity
from server.modules.release.bundle import content_ref_commit
from server.modules.release.models import Release
from server.modules.release.service import ReleaseSnapshot
from server.modules.release.snapshot_accessors import (
    snapshot_content_mode,
    snapshot_source_ref,
)
from server.modules.shared.formatting import utc_now_iso as _utc_now_iso


def _git_value(repo_root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def extract_git_context(repo_root: Path) -> dict:
    """Collect git metadata (branch, commit, remote) from the repository."""
    return {
        "repo_url": _git_value(repo_root, "config", "--get", "remote.origin.url"),
        "branch": _git_value(repo_root, "branch", "--show-current"),
        "upstream": _git_value(repo_root, "rev-parse", "--abbrev-ref", "@{upstream}"),
        "head_commit": _git_value(repo_root, "rev-parse", "HEAD"),
    }


def _build_source_snapshot(
    *,
    snapshot: ReleaseSnapshot,
    release_marker: str,
    source_ref: str,
    source_commit: str,
    git_ctx: dict[str, Any],
) -> dict[str, Any]:
    """Build the source_snapshot sub-document."""
    mode = snapshot_content_mode(snapshot)
    return {
        "kind": "uploaded-bundle" if mode == "uploaded_bundle" else "content-ref",
        "tag": release_marker,
        "ref": source_ref,
        "commit": source_commit,
        "remote": git_ctx["repo_url"],
        "upstream": git_ctx["upstream"],
        "immutable": True,
        "pushed": False,
    }


def _build_registry_payload(
    *,
    repo_root: Path,
    release_marker: str,
    release_ref: str,
    source_commit: str,
    git_ctx: dict,
) -> dict:
    """Build the registry resolved-entry sub-document."""
    return {
        "default_registry": "hosted",
        "registries_consulted": ["hosted"],
        "resolved": [
            {
                "registry_name": "hosted",
                "registry_kind": "http",
                "registry_url": None,
                "registry_host": None,
                "registry_priority": 100,
                "registry_trust": "private",
                "registry_root": str(repo_root),
                "registry_pin_mode": "server-generated",
                "registry_pin_value": release_marker,
                "registry_ref": release_ref,
                "registry_allowed_refs": [],
                "registry_allowed_hosts": [],
                "registry_update_mode": "server-managed",
                "registry_commit": git_ctx["head_commit"] or source_commit,
                "registry_tag": release_marker,
                "registry_branch": git_ctx["branch"],
                "registry_origin_url": git_ctx["repo_url"],
                "registry_origin_host": None,
            }
        ],
    }


def _build_dependency_step(
    *,
    publisher: str,
    skill_slug: str,
    qualified_name: str,
    version: str,
    source_ref: str,
    source_snapshot: dict,
    manifest_public_path: str,
    bundle_public_path: str,
    bundle_sha256: str,
    source_commit: str,
    release_marker: str,
) -> dict:
    """Build a single dependency step entry."""
    return {
        "order": 1,
        "name": skill_slug,
        "publisher": publisher,
        "qualified_name": qualified_name,
        "identity_mode": "qualified",
        "version": version,
        "registry": "hosted",
        "stage": "sealed",
        "path": source_ref,
        "skill_path": source_ref,
        "relative_path": None,
        "source_type": source_snapshot["kind"],
        "distribution_manifest": manifest_public_path,
        "distribution_bundle": bundle_public_path,
        "distribution_bundle_sha256": bundle_sha256,
        "distribution_attestation": None,
        "distribution_attestation_signature": None,
        "action": "install",
        "needs_apply": True,
        "requested_by": [],
        "depends_on": [],
        "conflicts_with": [],
        "root": True,
        "source_commit": source_commit,
        "source_ref": source_ref,
        "source_tag": release_marker,
        "source_snapshot_kind": source_snapshot["kind"],
        "source_snapshot_tag": source_snapshot["tag"],
        "source_snapshot_ref": source_snapshot["ref"],
        "source_snapshot_commit": source_snapshot["commit"],
    }


def _skill_payload(
    snapshot: ReleaseSnapshot,
    publisher: str,
    skill_slug: str,
    qualified_name: str,
    version: str,
) -> dict[str, Any]:
    return {
        "name": skill_slug,
        "publisher": publisher,
        "qualified_name": qualified_name,
        "identity_mode": "qualified",
        "version": version,
        "status": "active",
        "summary": snapshot.skill.summary,
        "path": f"server-generated/{publisher}/{skill_slug}",
        "author": publisher,
        "owners": [publisher],
        "maintainers": [publisher],
        "depends_on": [],
        "conflicts_with": [],
    }


def _git_payload(
    git_ctx: dict, source_commit: str, release_marker: str, release_ref: str, signer: str
) -> dict:
    return {
        "repo_url": git_ctx["repo_url"],
        "branch": git_ctx["branch"],
        "upstream": git_ctx["upstream"],
        "commit": source_commit,
        "head_commit": git_ctx["head_commit"],
        "expected_tag": release_marker,
        "release_ref": release_ref,
        "remote": None,
        "remote_tag_object": None,
        "remote_tag_commit": None,
        "signed_tag_verified": True,
        "tag_signer": signer,
    }


def _dependencies_payload(
    *,
    skill_slug: str,
    publisher: str,
    qualified_name: str,
    version: str,
    source_ref: str,
    source_snapshot: dict,
    manifest_public_path: str,
    dependency_step: dict,
) -> dict:
    return {
        "mode": "install",
        "root": {
            "name": skill_slug,
            "publisher": publisher,
            "qualified_name": qualified_name,
            "version": version,
            "registry": "hosted",
            "stage": "sealed",
            "path": source_ref,
            "source_type": source_snapshot["kind"],
            "distribution_manifest": manifest_public_path,
            "source_snapshot_tag": source_snapshot["tag"],
            "source_snapshot_commit": source_snapshot["commit"],
        },
        "steps": [dependency_step],
        "registries_consulted": ["hosted"],
    }


def _review_payload() -> dict:
    return {
        "reviewers": [],
        "effective_review_state": "not_applicable",
        "required_approvals": 0,
        "required_groups": [],
        "covered_groups": [],
        "missing_groups": [],
        "approval_count": 0,
        "blocking_rejection_count": 0,
        "quorum_met": True,
        "review_gate_pass": True,
        "latest_decisions": [],
        "ignored_decisions": [],
        "configured_groups": {},
    }


def _release_payload(releaser: str | None, signer: str) -> dict:
    return {
        "releaser_identity": releaser,
        "release_mode": "local-tag",
        "transfer_required": False,
        "transfer_authorized": True,
        "authorized_signers": [signer],
        "authorized_releasers": [releaser] if releaser else [],
        "transfer_matches": [],
        "competing_claims": [],
    }


def _attestation_payload(config: dict, signature_filename: str, signer: str) -> dict:
    return {
        "format": config["format"],
        "namespace": config["namespace"],
        "allowed_signers": config["allowed_signers_rel"],
        "signature_file": signature_filename,
        "signature_ext": config["signature_ext"],
        "signer_identity": signer,
        "policy_mode": config["policy_mode"],
        "require_verified_attestation_for_release_output": config["require_release_output"],
        "require_verified_attestation_for_distribution": config["require_distribution"],
    }


def _distribution_payload(
    path: str, sha256: str, size: int, root_dir: str, file_count: int, manifest_path: str
) -> dict:
    return {
        "manifest_path": manifest_path,
        "bundle": {
            "path": path,
            "format": "tar.gz",
            "sha256": sha256,
            "size": size,
            "root_dir": root_dir,
            "file_count": file_count,
        },
    }


def build_provenance_payload(
    *,
    snapshot: ReleaseSnapshot,
    release: Release,
    repo_root: Path,
    bundle_public_path: str,
    manifest_public_path: str,
    bundle_sha256: str,
    bundle_size: int,
    bundle_root_dir: str,
    bundle_file_count: int,
    signature_filename: str,
    attestation_cfg: dict[str, Any],
    signer_identity: str,
) -> dict[str, Any]:
    """Build the signed provenance document for a hosted release."""
    publisher = snapshot.namespace.slug
    skill_slug = snapshot.skill.slug
    version = snapshot.skill_version.version
    qualified_name = f"{publisher}/{skill_slug}"
    release_marker = f"registry/{qualified_name}/v{version}"
    release_ref = f"refs/registry-releases/{qualified_name}/{version}"

    git_ctx = extract_git_context(repo_root)
    source_ref = snapshot_source_ref(snapshot)
    source_commit = content_ref_commit(
        source_ref,
        snapshot.skill_version.content_digest,
    )
    source_snapshot = _build_source_snapshot(
        snapshot=snapshot,
        release_marker=release_marker,
        source_ref=source_ref,
        source_commit=source_commit,
        git_ctx=git_ctx,
    )
    registry_payload = _build_registry_payload(
        repo_root=repo_root,
        release_marker=release_marker,
        release_ref=release_ref,
        source_commit=source_commit,
        git_ctx=git_ctx,
    )
    dependency_step = _build_dependency_step(
        publisher=publisher,
        skill_slug=skill_slug,
        qualified_name=qualified_name,
        version=version,
        source_ref=source_ref,
        source_snapshot=source_snapshot,
        manifest_public_path=manifest_public_path,
        bundle_public_path=bundle_public_path,
        bundle_sha256=bundle_sha256,
        source_commit=source_commit,
        release_marker=release_marker,
    )
    releaser = resolve_releaser_identity(repo_root)
    return {
        "$schema": "schemas/provenance.schema.json",
        "schema_version": 1,
        "kind": "skill-release-attestation",
        "generated_at": _utc_now_iso(),
        "skill": _skill_payload(snapshot, publisher, skill_slug, qualified_name, version),
        "git": _git_payload(git_ctx, source_commit, release_marker, release_ref, signer_identity),
        "source_snapshot": source_snapshot,
        "registry": registry_payload,
        "dependencies": _dependencies_payload(
            skill_slug=skill_slug,
            publisher=publisher,
            qualified_name=qualified_name,
            version=version,
            source_ref=source_ref,
            source_snapshot=source_snapshot,
            manifest_public_path=manifest_public_path,
            dependency_step=dependency_step,
        ),
        "review": _review_payload(),
        "release": _release_payload(releaser, signer_identity),
        "attestation": _attestation_payload(attestation_cfg, signature_filename, signer_identity),
        "distribution": _distribution_payload(
            bundle_public_path,
            bundle_sha256,
            bundle_size,
            bundle_root_dir,
            bundle_file_count,
            manifest_public_path,
        ),
        "release_snapshot": {
            "release_id": release.id,
            "skill_version_id": snapshot.skill_version.id,
            "source": "version",
        },
    }
