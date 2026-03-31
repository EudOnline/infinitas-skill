from __future__ import annotations

from tests.helpers.installed_integrity import (
    assert_installed_integrity_clean_drift_and_repair,
    assert_installed_integrity_docs_exist,
    assert_installed_integrity_stale_mutation_guardrails,
)


def test_installed_integrity_clean_drift_and_repair() -> None:
    assert_installed_integrity_clean_drift_and_repair()


def test_installed_integrity_stale_mutation_guardrails() -> None:
    assert_installed_integrity_stale_mutation_guardrails()


def test_installed_integrity_docs_exist() -> None:
    assert_installed_integrity_docs_exist()


def main() -> None:
    assert_installed_integrity_clean_drift_and_repair()
    assert_installed_integrity_stale_mutation_guardrails()
    assert_installed_integrity_docs_exist()
