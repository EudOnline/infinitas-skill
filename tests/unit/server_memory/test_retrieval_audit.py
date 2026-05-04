from __future__ import annotations

from src.infinitas_skill.server.memory_retrieval_audit import _aggregate_id


class TestAggregateId:
    def test_recommend_operation(self):
        entry = {
            "operation": "recommend",
            "task": "find skill",
            "target_agent": "codex",
            "results": {"top_qualified_name": "acme/skill"},
        }
        result = _aggregate_id(entry)
        assert result.startswith("mr:")
        assert len(result) == 43  # "mr:" + 40 hex chars

    def test_other_operation(self):
        entry = {
            "operation": "inspect",
            "skill_ref": "acme/skill",
            "version": "1.0.0",
            "target_agent": "codex",
        }
        result = _aggregate_id(entry)
        assert result.startswith("mr:")

    def test_defaults_for_missing_fields(self):
        entry = {"operation": "inspect"}
        result = _aggregate_id(entry)
        assert result.startswith("mr:")
