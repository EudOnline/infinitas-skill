from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_make_targets_and_docs_expose_dev_workflow_entrypoints() -> None:
    makefile = _read("Makefile")
    lint_command = (
        "uv run ruff check src/infinitas_skill server/ui server/app.py tests/integration tests/unit"
    )
    fmt_command = (
        "uv run ruff format src/infinitas_skill server/ui server/app.py tests/integration tests/unit"
    )
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
    assert (
        "lint-maintained:\n"
        f"\t{lint_command}\n"
    ) in makefile, "Makefile lint-maintained should match requested command exactly"
    assert (
        "fmt-maintained:\n"
        f"\t{fmt_command}\n"
    ) in makefile, "Makefile fmt-maintained should match requested command exactly"

    readme = _read("README.md")
    assert "make test-fast" in readme, "README.md should mention make test-fast"
    assert "make test-full" in readme, "README.md should mention make test-full"
    assert lint_command in readme, "README.md should include raw lint-maintained fallback command"

    testing_doc = _read("docs/reference/testing.md")
    assert "make lint-maintained" in testing_doc, (
        "docs/reference/testing.md should mention make lint-maintained"
    )
    assert "uv sync" in testing_doc, (
        "docs/reference/testing.md should include bootstrap raw fallback (uv sync)"
    )
    assert lint_command in testing_doc, (
        "docs/reference/testing.md should include lint-maintained raw fallback"
    )

    pyproject = _read("pyproject.toml")
    assert 'select = ["E", "F", "I"]' in pyproject, (
        "pyproject.toml should configure Ruff lint select"
    )
    assert "ignore =" not in pyproject, (
        "pyproject.toml should not define Ruff ignore rules for this task"
    )
