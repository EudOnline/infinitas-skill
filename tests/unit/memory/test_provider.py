from __future__ import annotations

from infinitas_skill.memory.config import MemoryConfig
from infinitas_skill.memory.contracts import MemoryRecord
from infinitas_skill.memory.memo0_provider import Memo0MemoryProvider
from infinitas_skill.memory.provider import build_memory_provider
from server.settings import get_settings


def test_disabled_backend_returns_noop_provider(monkeypatch):
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "disabled")
    provider = build_memory_provider()
    assert provider.backend_name == "noop"


def test_memo0_backend_without_sdk_falls_back_to_noop(monkeypatch):
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "memo0")
    provider = build_memory_provider(importer=lambda: (_ for _ in ()).throw(ImportError()))
    assert provider.backend_name == "noop"
    assert provider.capabilities["write"] is False


def test_unsupported_backend_reports_specific_noop_reason(monkeypatch):
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "future-backend")
    provider = build_memory_provider()
    assert provider.backend_name == "noop"
    assert provider.reason == "unsupported memory backend: future-backend"


def test_memo0_init_runtime_failure_keeps_noop_with_detailed_reason(monkeypatch):
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "memo0")
    provider = build_memory_provider(
        importer=lambda: (_ for _ in ()).throw(RuntimeError("network unavailable"))
    )
    assert provider.backend_name == "noop"
    assert provider.reason == "memo0 provider initialization failed: network unavailable"


def test_settings_read_memory_flags(monkeypatch):
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "memo0")
    monkeypatch.setenv("INFINITAS_MEMORY_CONTEXT_ENABLED", "1")
    monkeypatch.setenv("INFINITAS_MEMORY_WRITE_ENABLED", "1")
    settings = get_settings()
    assert settings.memory_backend == "memo0"
    assert settings.memory_context_enabled is True
    assert settings.memory_write_enabled is True


class _FakeMemo0Client:
    def __init__(self):
        self.add_calls = []

    def add(self, **payload):
        self.add_calls.append(payload)
        return {"id": "memory-1"}

    def search(self, **_payload):
        return {
            "results": [
                {
                    "id": "memory-1",
                    "memory": "Prefer release flow",
                    "metadata": {"memory_type": "experience"},
                }
            ]
        }


class _FakeMemo0Module:
    def __init__(self, client):
        self._client = client

    def MemoryClient(self, **_kwargs):
        return self._client


def test_memo0_provider_persists_and_recovers_memory_type():
    client = _FakeMemo0Client()
    provider = Memo0MemoryProvider.from_config(
        config=MemoryConfig(
            backend="memo0",
            context_enabled=True,
            write_enabled=True,
            namespace="infinitas",
            top_k=5,
            mem0_base_url=None,
            mem0_api_key_env="MEM0_API_KEY",
        ),
        importer=lambda: _FakeMemo0Module(client),
    )

    result = provider.add(
        record=MemoryRecord(memory="Prefer release flow", memory_type="experience"),
        scope={"user_ref": "maintainer"},
    )

    assert result.memory_id == "memory-1"
    assert client.add_calls[0]["metadata"]["memory_type"] == "experience"
    assert client.add_calls[0]["metadata"]["user_ref"] == "maintainer"

    search_result = provider.search(
        query="release flow",
        limit=5,
        scope={"user_ref": "maintainer"},
        memory_types=["experience"],
    )
    assert search_result.records[0].memory_type == "experience"
