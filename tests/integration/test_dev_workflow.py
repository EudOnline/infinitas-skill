from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_make_targets_and_docs_expose_dev_workflow_entrypoints() -> None:
    makefile = _read("Makefile")
    required_targets = [
        "bootstrap",
        "test-fast",
        "test-full",
        "lint-maintained",
        "fmt-maintained",
        "doctor",
    ]
    for target in required_targets:
        assert re.search(rf"^{re.escape(target)}\s*:", makefile, flags=re.MULTILINE), (
            f"expected Makefile target '{target}'"
        )

    readme = _read("README.md")
    assert "make test-fast" in readme, "README.md should mention make test-fast"
    assert "make test-full" in readme, "README.md should mention make test-full"

    testing_doc = _read("docs/reference/testing.md")
    assert "make lint-maintained" in testing_doc, (
        "docs/reference/testing.md should mention make lint-maintained"
    )
