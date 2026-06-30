from __future__ import annotations

from pathlib import Path

import pytest

from infinitas_skill.cli.reference import render_cli_reference

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.governance


def test_cli_reference_doc_matches_generated_argparse_output() -> None:
    target = ROOT / "docs" / "reference" / "cli-reference.md"
    actual = target.read_text(encoding="utf-8")
    expected = render_cli_reference()
    assert actual == expected, (
        "docs/reference/cli-reference.md is out of date; "
        "regenerate with: uv run python3 -m infinitas_skill.cli.reference > "
        "docs/reference/cli-reference.md"
    )
