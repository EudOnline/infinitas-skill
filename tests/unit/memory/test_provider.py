from __future__ import annotations

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


def test_settings_read_memory_flags(monkeypatch):
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "memo0")
    monkeypatch.setenv("INFINITAS_MEMORY_CONTEXT_ENABLED", "1")
    monkeypatch.setenv("INFINITAS_MEMORY_WRITE_ENABLED", "1")
    settings = get_settings()
    assert settings.memory_backend == "memo0"
    assert settings.memory_context_enabled is True
    assert settings.memory_write_enabled is True
