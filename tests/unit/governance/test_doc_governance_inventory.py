"""Real-doc inventory checks for document governance.

Parametrizes the shared ruleset in tests.helpers.doc_governance over every
maintained/legacy doc discovered in the live tree. The synthetic-fixture edge
cases live in tests/integration/test_doc_governance.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import doc_governance as dg

pytestmark = pytest.mark.governance

MAINTAINED_DOCS = dg.maintained_docs()
LEGACY_DOCS = dg.legacy_docs()
_MAINTAINED_IDS = [str(p.relative_to(dg.ROOT)) for p, _ in MAINTAINED_DOCS]
_LEGACY_IDS = [str(p.relative_to(dg.ROOT)) for p, _ in LEGACY_DOCS]


def test_root_docs_restricted_to_allowlist() -> None:
    dg.check_root_allowlist()


def test_at_least_one_maintained_document() -> None:
    assert MAINTAINED_DOCS


def test_at_least_one_indexed_legacy_document() -> None:
    assert LEGACY_DOCS


def test_readme_has_maintained_surface_inventory() -> None:
    dg.ensure_readme_has_maintained_surface_inventory()


def test_docs_index_does_not_expose_legacy_ai_landing() -> None:
    dg.ensure_docs_index_does_not_expose_legacy_ai_landing()


@pytest.mark.parametrize("rel", [str(p) for p in dg.REMOVED_OPERATOR_SHIMS])
def test_removed_operator_shim_stays_deleted(rel: str) -> None:
    assert not (dg.ROOT / rel).exists(), f"removed operator shim must stay deleted: {rel}"


@pytest.mark.parametrize("rel", [str(p) for p in dg.REMOVED_LEGACY_DOC_ANNEXES])
def test_removed_legacy_doc_annex_stays_deleted(rel: str) -> None:
    assert not (dg.ROOT / rel).exists(), f"removed legacy doc annex must stay deleted: {rel}"


@pytest.mark.parametrize("path,metadata", MAINTAINED_DOCS, ids=_MAINTAINED_IDS)
def test_maintained_doc_in_allowed_location(path: Path, metadata: dict[str, str]) -> None:
    dg.ensure_allowed_location(path)


@pytest.mark.parametrize("path,metadata", MAINTAINED_DOCS, ids=_MAINTAINED_IDS)
def test_maintained_doc_has_required_metadata(path: Path, metadata: dict[str, str]) -> None:
    dg.ensure_required_metadata(path, metadata)


@pytest.mark.parametrize("path,metadata", MAINTAINED_DOCS, ids=_MAINTAINED_IDS)
def test_maintained_doc_linked_from_landing(path: Path, metadata: dict[str, str]) -> None:
    dg.ensure_landing_coverage(path)


@pytest.mark.parametrize("path,metadata", MAINTAINED_DOCS, ids=_MAINTAINED_IDS)
def test_maintained_doc_has_no_worktree_links(path: Path, metadata: dict[str, str]) -> None:
    dg.ensure_no_worktree_links(path)


@pytest.mark.parametrize("path,metadata", MAINTAINED_DOCS, ids=_MAINTAINED_IDS)
def test_maintained_doc_legacy_mentions_have_canonical_entrypoints(
    path: Path, metadata: dict[str, str]
) -> None:
    dg.ensure_legacy_command_mentions_have_canonical_entrypoints(path)


@pytest.mark.parametrize("path,metadata", LEGACY_DOCS, ids=_LEGACY_IDS)
def test_legacy_doc_metadata(path: Path, metadata: dict[str, str]) -> None:
    dg.ensure_legacy_metadata(path, metadata)


@pytest.mark.parametrize("path,metadata", LEGACY_DOCS, ids=_LEGACY_IDS)
def test_legacy_doc_linked_from_landing(path: Path, metadata: dict[str, str]) -> None:
    dg.ensure_legacy_landing_coverage(path)


@pytest.mark.parametrize("path,metadata", LEGACY_DOCS, ids=_LEGACY_IDS)
def test_legacy_doc_has_no_worktree_links(path: Path, metadata: dict[str, str]) -> None:
    dg.ensure_no_worktree_links(path)
