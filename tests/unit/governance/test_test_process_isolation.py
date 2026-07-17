from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_contract_test_groups_run_in_independent_pytest_processes() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipe = makefile.split("test-contracts:\n", 1)[1].split("\n\ntest-full:", 1)[0]

    expected_commands = [
        "\t.venv/bin/pytest tests/unit -q --override-ini=addopts=",
        "\t.venv/bin/pytest tests/security -q --override-ini=addopts=",
        "\t.venv/bin/pytest tests/performance -q --override-ini=addopts=",
        (
            "\t.venv/bin/pytest tests/integration/test_alembic_metadata.py "
            "-q --override-ini=addopts="
        ),
    ]

    for command in expected_commands:
        assert command in recipe
