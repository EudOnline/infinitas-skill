from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.infinitas_skill.server.memory_curation_queue import (
    build_memory_curation_job_summary,
    resolve_memory_curation_job_options,
)


class TestResolveMemoryCurationJobOptions:
    def test_defaults(self):
        result = resolve_memory_curation_job_options()
        assert result["action"] == "plan"
        assert result["apply"] is False
        assert result["limit"] == 50
        assert result["max_actions"] == 20
        assert result["actor_ref"] == "system:memory-curation"

    def test_custom_values(self):
        result = resolve_memory_curation_job_options(
            action="EXECUTE", apply=True, limit=10, max_actions=5, actor_ref="test"
        )
        assert result["action"] == "execute"
        assert result["apply"] is True
        assert result["limit"] == 10
        assert result["max_actions"] == 5
        assert result["actor_ref"] == "test"

    def test_invalid_limit(self):
        result = resolve_memory_curation_job_options(limit=-5)
        assert result["limit"] == 50

    def test_invalid_max_actions(self):
        result = resolve_memory_curation_job_options(max_actions=0)
        assert result["max_actions"] == 20

    def test_use_server_policy(self):
        with patch(
            "server.settings.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.memory_curation_action = "execute"
            settings.memory_curation_apply = True
            settings.memory_curation_limit = 100
            settings.memory_curation_max_actions = 50
            settings.memory_curation_actor_ref = "server"
            mock_settings.return_value = settings
            result = resolve_memory_curation_job_options(use_server_policy=True)
            assert result["action"] == "execute"
            assert result["apply"] is True
            assert result["limit"] == 100


class TestBuildMemoryCurationJobSummary:
    def test_builds_summary(self):
        job = MagicMock()
        job.id = 1
        job.kind = "memory_curation"
        job.status = "queued"
        job.note = "test note"
        job.payload_json = '{"action": "plan"}'
        result = build_memory_curation_job_summary(job)
        assert result["id"] == 1
        assert result["kind"] == "memory_curation"
        assert result["status"] == "queued"
        assert result["note"] == "test note"
        assert result["payload"] == {"action": "plan"}
