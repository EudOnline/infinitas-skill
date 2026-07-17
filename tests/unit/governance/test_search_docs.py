from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.governance

# search.js was modularized out of app.js (commit 4b69383); the inspect command
# string now lives in the module, not the orchestrator.
_CONSUME = "skills/active/consume-infinitas-skill/SKILL.md"
_FEDERATION = "skills/active/federation-registry-ops/SKILL.md"


@pytest.mark.parametrize(
    "rel,needle",
    [
        (_CONSUME, "uv run infinitas discovery search"),
        (_CONSUME, "uv run infinitas discovery recommend"),
        (_CONSUME, "uv run infinitas discovery inspect"),
        (_FEDERATION, "uv run infinitas discovery search"),
        (_FEDERATION, "uv run infinitas discovery inspect"),
        ("docs/reference/cli-reference.md", "infinitas discovery inspect"),
        ("docs/reference/cli-reference.md", "discovery inspect"),
        ("README.md", "docs/reference/cli-reference.md"),
        ("server/static/js/modules/search-results.js", "uv run infinitas discovery inspect"),
    ],
)
def test_search_doc_surface_mentions(rel: str, needle: str) -> None:
    assert needle in (ROOT / rel).read_text(encoding="utf-8")
