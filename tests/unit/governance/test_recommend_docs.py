from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.governance

_CONSUME_SKILL = "skills/active/consume-infinitas-skill/SKILL.md"
_CONSUME_SMOKE = "skills/active/consume-infinitas-skill/tests/smoke.md"


@pytest.mark.parametrize(
    "rel,needle",
    [
        ("README.md", "docs/reference/cli-reference.md"),
        ("README.md", "uv run infinitas discovery"),
        ("docs/README.md", "platform-contracts/README.md"),
        (_CONSUME_SKILL, "uv run infinitas discovery recommend"),
        (_CONSUME_SKILL, "uv run infinitas discovery inspect"),
        (_CONSUME_SMOKE, "uv run infinitas discovery recommend"),
        (_CONSUME_SMOKE, "--mode confirm"),
        ("docs/reference/cli-reference.md", "infinitas discovery recommend"),
        ("docs/reference/cli-reference.md", "infinitas discovery inspect"),
    ],
)
def test_recommend_doc_surface_mentions(rel: str, needle: str) -> None:
    assert needle in (ROOT / rel).read_text(encoding="utf-8")
