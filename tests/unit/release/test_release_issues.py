from __future__ import annotations

from infinitas_skill.release.release_issues import (
    apply_identity_warnings,
    apply_worktree_and_upstream_findings,
)


def test_apply_worktree_and_upstream_findings_adds_blocking_issues() -> None:
    issues: list[dict] = []
    warnings: list[str] = []

    apply_worktree_and_upstream_findings(
        issues=issues,
        warnings=warnings,
        dirty=True,
        require_clean_worktree=True,
        require_upstream_sync=True,
        branch="main",
        upstream="origin/main",
        ahead=2,
        behind=1,
    )

    ids = {item["id"] for item in issues}
    assert "dirty-worktree" in ids
    assert "ahead-of-upstream" in ids
    assert "behind-of-upstream" in ids
    assert not warnings


def test_apply_identity_warnings_reports_missing_identity_and_signer_mismatch() -> None:
    warnings: list[str] = []
    namespace_report = {
        "authorized_releasers": ["trusted-releaser"],
        "authorized_signers": ["trusted-signer"],
    }

    apply_identity_warnings(
        warnings=warnings,
        releaser_identity=None,
        namespace_report=namespace_report,
        identity={"qualified_name": "demo/skill", "name": "skill"},
        transparency_log={"error": "proof mismatch"},
        local_tag={"signer": "untrusted-signer"},
    )

    combined = "\n".join(warnings)
    assert "cannot determine releaser identity" in combined
    assert "transparency log proof could not be verified: proof mismatch" in combined
    assert (
        "tag signer 'untrusted-signer' is not listed in namespace-policy authorized_signers"
        in combined
    )
