from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.governance


@pytest.mark.parametrize(
    "rel,needle",
    [
        ("README.md", "policy_trace"),
        ("README.md", "validation_errors"),
        ("README.md", "policy/team-policy.json"),
        ("README.md", "uv run infinitas policy check-promotion <skill> --json"),
        ("README.md", "uv run infinitas release check-state operate-infinitas-skill --json"),
        ("README.md", "scripts/validate-registry.py --json"),
        ("docs/reference/policy-packs.md", "--debug-policy"),
        ("docs/reference/policy-packs.md", "policy_trace"),
        ("docs/reference/policy-packs.md", "validation_errors"),
        ("docs/reference/policy-packs.md", "team_policy"),
        ("docs/reference/policy-packs.md", "owner_teams"),
        ("docs/reference/policy-packs.md", "policy/team-policy.json"),
        ("docs/reference/policy-packs.md", "effective_sources"),
        ("docs/reference/policy-packs.md", "blocking_rules"),
    ],
)
def test_policy_trace_surface_mentions(rel: str, needle: str) -> None:
    assert needle in (ROOT / rel).read_text(encoding="utf-8")
