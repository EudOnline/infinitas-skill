from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.governance


@pytest.mark.parametrize(
    "rel,needle",
    [
        ("README.md", "policy/policy-packs.json"),
        ("docs/reference/policy-packs.md", "repository-local files win over packs"),
        ("docs/reference/policy-packs.md", "policy/packs/"),
        ("docs/reference/promotion-policy.md", "policy/policy-packs.json"),
        ("docs/ops/signing-bootstrap.md", "policy/policy-packs.json"),
        ("docs/reference/multi-registry.md", "policy/policy-packs.json"),
        ("scripts/check-all.sh", ".venv/bin/infinitas policy check-packs"),
    ],
)
def test_policy_pack_referenced_in_surface(rel: str, needle: str) -> None:
    assert needle in (ROOT / rel).read_text(encoding="utf-8")
