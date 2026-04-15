from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE_ENV_EXAMPLE = ROOT / ".env.compose.example"


def test_compose_env_example_includes_required_production_fields() -> None:
    env_text = COMPOSE_ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "INFINITAS_SERVER_ENV=production" in env_text
    assert 'INFINITAS_SERVER_ALLOWED_HOSTS=["127.0.0.1","localhost"]' in env_text
