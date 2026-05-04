from __future__ import annotations

from src.infinitas_skill.memory.config import (
    DEFAULT_MEMORY_BACKEND,
    DEFAULT_MEMORY_NAMESPACE,
    DEFAULT_MEMORY_TOP_K,
    _env_flag,
    _positive_int_or_default,
    load_memory_config,
    normalize_memory_backend,
)


class TestNormalizeMemoryBackend:
    def test_empty_returns_default(self):
        assert normalize_memory_backend("") == DEFAULT_MEMORY_BACKEND

    def test_none_returns_default(self):
        assert normalize_memory_backend(None) == DEFAULT_MEMORY_BACKEND

    def test_whitespace_trimmed(self):
        assert normalize_memory_backend("  MEM0  ") == "mem0"


class TestEnvFlag:
    def test_true_values(self):
        for val in ["1", "true", "yes", "on", "TRUE"]:
            assert _env_flag(val) is True

    def test_false_values(self):
        for val in ["0", "false", "no", "", None]:
            assert _env_flag(val) is False


class TestPositiveIntOrDefault:
    def test_valid(self):
        assert _positive_int_or_default("10", 5) == 10

    def test_invalid(self):
        assert _positive_int_or_default("abc", 5) == 5

    def test_zero(self):
        assert _positive_int_or_default("0", 5) == 5

    def test_negative(self):
        assert _positive_int_or_default("-1", 5) == 5


class TestLoadMemoryConfig:
    def test_defaults(self):
        config = load_memory_config({})
        assert config.backend == DEFAULT_MEMORY_BACKEND
        assert config.namespace == DEFAULT_MEMORY_NAMESPACE
        assert config.top_k == DEFAULT_MEMORY_TOP_K
        assert config.context_enabled is False
        assert config.write_enabled is False

    def test_custom_values(self):
        config = load_memory_config(
            {
                "INFINITAS_MEMORY_BACKEND": "mem0",
                "INFINITAS_MEMORY_CONTEXT_ENABLED": "1",
                "INFINITAS_MEMORY_WRITE_ENABLED": "true",
                "INFINITAS_MEMORY_NAMESPACE": "test",
                "INFINITAS_MEMORY_TOP_K": "10",
                "INFINITAS_MEMORY_MEM0_BASE_URL": "http://localhost",
                "INFINITAS_MEMORY_MEM0_API_KEY_ENV": "CUSTOM_KEY",
            }
        )
        assert config.backend == "mem0"
        assert config.context_enabled is True
        assert config.write_enabled is True
        assert config.namespace == "test"
        assert config.top_k == 10
        assert config.mem0_base_url == "http://localhost"
        assert config.mem0_api_key_env == "CUSTOM_KEY"
