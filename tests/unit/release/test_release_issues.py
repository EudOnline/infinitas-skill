from __future__ import annotations

from src.infinitas_skill.release.release_issues import (
    apply_identity_findings,
    apply_platform_support_findings,
    apply_preflight_signer_warning,
    apply_worktree_and_upstream_findings,
    issue,
)


class TestIssue:
    def test_basic(self):
        result = issue("rule-1", "message text")
        assert result["id"] == "rule-1"
        assert result["message"] == "message text"
        assert result["rule"] == "message text"

    def test_with_rule(self):
        result = issue("rule-1", "message text", rule="custom rule")
        assert result["rule"] == "custom rule"


class TestApplyPlatformSupportFindings:
    def test_platform_error_with_requirement(self):
        issues = []
        warnings = []
        apply_platform_support_findings(
            issues=issues,
            warnings=warnings,
            require_fresh_platform_support=True,
            platform_compatibility={},
            platform_error=Exception("network error"),
        )
        assert len(issues) == 1
        assert "network error" in issues[0]["message"]

    def test_platform_error_without_requirement(self):
        issues = []
        warnings = []
        apply_platform_support_findings(
            issues=issues,
            warnings=warnings,
            require_fresh_platform_support=False,
            platform_compatibility={},
            platform_error=Exception("network error"),
        )
        assert len(warnings) == 1
        assert len(issues) == 0

    def test_blocking_platforms(self):
        issues = []
        warnings = []
        apply_platform_support_findings(
            issues=issues,
            warnings=warnings,
            require_fresh_platform_support=True,
            platform_compatibility={
                "blocking_platforms": [
                    {"platform": "py311", "state": "broken", "freshness_state": "stale"}
                ]
            },
        )
        assert len(issues) == 1
        assert "platform verified support is stale" in issues[0]["message"]


class TestApplyIdentityFindings:
    def test_missing_identity_enforced(self):
        issues = []
        warnings = []
        apply_identity_findings(
            issues=issues,
            warnings=warnings,
            mode="preflight",
            releaser_identity=None,
            namespace_report={"authorized_releasers": ["alice"]},
            identity={"name": "test-skill"},
            transparency_log={},
            local_tag={},
        )
        assert len(issues) == 1
        assert "cannot determine releaser identity" in issues[0]["message"]

    def test_unauthorized_releaser(self):
        issues = []
        warnings = []
        apply_identity_findings(
            issues=issues,
            warnings=warnings,
            mode="preflight",
            releaser_identity="bob",
            namespace_report={"authorized_releasers": ["alice"]},
            identity={"name": "test-skill"},
            transparency_log={},
            local_tag={},
        )
        assert len(issues) == 1
        assert "not listed" in issues[0]["message"]

    def test_transparency_log_error(self):
        issues = []
        warnings = []
        apply_identity_findings(
            issues=issues,
            warnings=warnings,
            mode="dev",
            releaser_identity="alice",
            namespace_report={},
            identity={},
            transparency_log={"error": "proof missing"},
            local_tag={},
        )
        assert len(warnings) == 1
        assert "proof could not be verified" in warnings[0]

    def test_unauthorized_signer(self):
        issues = []
        warnings = []
        apply_identity_findings(
            issues=issues,
            warnings=warnings,
            mode="dev",
            releaser_identity="alice",
            namespace_report={"authorized_signers": ["alice"]},
            identity={"name": "test-skill"},
            transparency_log={},
            local_tag={"signer": "bob"},
        )
        assert len(warnings) == 1
        assert "tag signer" in warnings[0]


class TestApplyWorktreeAndUpstreamFindings:
    def test_dirty_worktree_required(self):
        issues = []
        warnings = []
        apply_worktree_and_upstream_findings(
            issues=issues,
            warnings=warnings,
            dirty=True,
            require_clean_worktree=True,
            require_upstream_sync=True,
            branch="main",
            upstream="origin/main",
            ahead=0,
            behind=0,
        )
        assert len(issues) == 1
        assert "dirty-worktree" == issues[0]["id"]

    def test_dirty_worktree_optional(self):
        issues = []
        warnings = []
        apply_worktree_and_upstream_findings(
            issues=issues,
            warnings=warnings,
            dirty=True,
            require_clean_worktree=False,
            require_upstream_sync=False,
            branch="main",
            upstream="origin/main",
            ahead=0,
            behind=0,
        )
        assert len(warnings) == 1
        assert len(issues) == 0

    def test_missing_upstream(self):
        issues = []
        warnings = []
        apply_worktree_and_upstream_findings(
            issues=issues,
            warnings=warnings,
            dirty=False,
            require_clean_worktree=True,
            require_upstream_sync=True,
            branch="main",
            upstream=None,
            ahead=0,
            behind=0,
        )
        assert any(i["id"] == "missing-upstream" for i in issues)

    def test_ahead_of_upstream(self):
        issues = []
        warnings = []
        apply_worktree_and_upstream_findings(
            issues=issues,
            warnings=warnings,
            dirty=False,
            require_clean_worktree=True,
            require_upstream_sync=True,
            branch="main",
            upstream="origin/main",
            ahead=2,
            behind=0,
        )
        assert any(i["id"] == "ahead-of-upstream" for i in issues)

    def test_behind_upstream(self):
        issues = []
        warnings = []
        apply_worktree_and_upstream_findings(
            issues=issues,
            warnings=warnings,
            dirty=False,
            require_clean_worktree=True,
            require_upstream_sync=True,
            branch="main",
            upstream="origin/main",
            ahead=0,
            behind=3,
        )
        assert any(i["id"] == "behind-of-upstream" for i in issues)

    def test_behind_upstream_not_required(self):
        issues = []
        warnings = []
        apply_worktree_and_upstream_findings(
            issues=issues,
            warnings=warnings,
            dirty=False,
            require_clean_worktree=True,
            require_upstream_sync=False,
            branch="main",
            upstream="origin/main",
            ahead=0,
            behind=3,
        )
        assert len(issues) == 0
        assert any("behind" in w for w in warnings)


class TestApplyPreflightSignerWarning:
    def test_no_signer_entries(self):
        warnings = []
        apply_preflight_signer_warning(
            warnings=warnings,
            mode="preflight",
            allowed_signer_entries=[],
            allowed_signers_rel="policy/signing.json",
        )
        assert len(warnings) == 1
        assert "no signer entries" in warnings[0]

    def test_non_preflight_mode(self):
        warnings = []
        apply_preflight_signer_warning(
            warnings=warnings,
            mode="stable-release",
            allowed_signer_entries=[],
            allowed_signers_rel="policy/signing.json",
        )
        assert len(warnings) == 0

    def test_has_signer_entries(self):
        warnings = []
        apply_preflight_signer_warning(
            warnings=warnings,
            mode="preflight",
            allowed_signer_entries=[{"key": "abc"}],
            allowed_signers_rel="policy/signing.json",
        )
        assert len(warnings) == 0
