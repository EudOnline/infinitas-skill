from __future__ import annotations

from src.infinitas_skill.discovery.agent_support import supports_target_agent


class TestSupportsTargetAgent:
    def test_none_target(self):
        assert supports_target_agent({}, None) is True

    def test_blocking_state(self):
        item = {"verified_support": {"codex": {"state": "blocked"}}}
        assert supports_target_agent(item, "codex") is False

    def test_verified_state(self):
        item = {"verified_support": {"codex": {"state": "native"}}}
        assert supports_target_agent(item, "codex") is True

    def test_openclaw_ready(self):
        item = {
            "runtime": {"platform": "openclaw", "readiness": {"ready": True}},
        }
        assert supports_target_agent(item, "openclaw") is True

    def test_agent_compatible_fallback(self):
        item = {"agent_compatible": ["codex", "claude"]}
        assert supports_target_agent(item, "codex") is True

    def test_not_compatible(self):
        item = {"agent_compatible": ["claude"]}
        assert supports_target_agent(item, "codex") is False

    def test_no_data(self):
        item = {}
        assert supports_target_agent(item, "codex") is False
