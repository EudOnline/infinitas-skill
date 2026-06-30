from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.governance


@pytest.mark.parametrize(
    "rel,needle",
    [
        ("docs/reference/release-attestation.md", "Offline verification"),
        ("docs/reference/release-attestation.md", "Online verification"),
        ("docs/reference/release-attestation.md", "scripts/verify-attestation.py"),
        ("docs/reference/release-attestation.md", "scripts/verify-ci-attestation.py"),
        ("docs/reference/release-attestation.md", "scripts/verify-distribution-manifest.py"),
        ("docs/reference/release-attestation.md", "`ssh`"),
        ("docs/reference/release-attestation.md", "`ci`"),
        ("docs/reference/release-attestation.md", "`both`"),
        ("docs/reference/release-attestation.md", "release_trust_mode"),
        ("docs/reference/release-attestation.md", "CI-native attestation"),
        ("docs/reference/release-attestation.md", "required_formats"),
        ("docs/reference/release-attestation.md", "CI attestation"),
        ("docs/ops/release-checklist.md", "CI attestation"),
        ("docs/ops/release-checklist.md", "`release_trust_mode`"),
        ("docs/ops/release-checklist.md", "`both`"),
        ("README.md", "scripts/verify-ci-attestation.py"),
        ("README.md", "release-attestation.yml"),
        ("README.md", "CI-native attestation"),
    ],
)
def test_ci_attestation_doc_surface_mentions(rel: str, needle: str) -> None:
    assert needle in (ROOT / rel).read_text(encoding="utf-8")
