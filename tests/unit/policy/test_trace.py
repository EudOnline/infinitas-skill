from __future__ import annotations

from src.infinitas_skill.policy.trace import build_policy_trace, render_policy_trace


class TestBuildPolicyTrace:
    def test_basic(self):
        trace = build_policy_trace(
            domain="release",
            decision="allow",
            summary="All checks passed",
        )
        assert trace["domain"] == "release"
        assert trace["decision"] == "allow"
        assert trace["summary"] == "All checks passed"

    def test_empty_summary(self):
        trace = build_policy_trace(domain="test", decision="deny", summary="")
        assert trace["summary"] == ""

    def test_with_lists(self):
        trace = build_policy_trace(
            domain="release",
            decision="allow",
            summary="OK",
            reasons=["reason1", "reason2", "reason1"],
            next_actions=["act1"],
        )
        assert trace["reasons"] == ["reason1", "reason2"]
        assert trace["next_actions"] == ["act1"]

    def test_with_rules(self):
        trace = build_policy_trace(
            domain="release",
            decision="allow",
            summary="OK",
            applied_rules=["rule1", {"rule": "rule2", "message": "msg"}],
        )
        assert len(trace["applied_rules"]) == 2
        assert trace["applied_rules"][0] == {"rule": "rule1"}
        assert trace["applied_rules"][1]["rule"] == "rule2"


class TestRenderPolicyTrace:
    def test_basic(self):
        result = render_policy_trace(
            {
                "domain": "release",
                "decision": "allow",
                "summary": "OK",
            }
        )
        assert "policy domain: release" in result
        assert "decision: allow" in result
        assert "summary: OK" in result

    def test_empty_trace(self):
        result = render_policy_trace({})
        assert "policy domain: -" in result

    def test_with_sources(self):
        result = render_policy_trace(
            {
                "domain": "release",
                "decision": "allow",
                "summary": "OK",
                "effective_sources": [
                    {"name": "policy.json", "path": "/path/to/policy.json"},
                ],
            }
        )
        assert "effective_sources:" in result
        assert "policy.json" in result

    def test_with_rules(self):
        result = render_policy_trace(
            {
                "domain": "release",
                "decision": "allow",
                "summary": "OK",
                "applied_rules": [{"rule": "needs-review"}],
                "blocking_rules": [{"rule": "missing-signature"}],
            }
        )
        assert "applied_rules:" in result
        assert "blocking_rules:" in result

    def test_with_exceptions(self):
        result = render_policy_trace(
            {
                "domain": "release",
                "decision": "allow",
                "summary": "OK",
                "exceptions": [
                    {"id": "EX-1", "justification": "legacy", "expires_at": "2026-01-01"},
                ],
            }
        )
        assert "exceptions:" in result
        assert "EX-1" in result
        assert "justification=legacy" in result

    def test_non_dict_input(self):
        result = render_policy_trace(None)
        assert "policy domain: -" in result
