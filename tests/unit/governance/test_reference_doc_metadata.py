from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.governance

REQUIRED_FIELDS = ["audience", "owner", "source_of_truth", "last_reviewed", "status"]

TARGETS = [
    ROOT / "docs" / "reference" / "README.md",
    ROOT / "docs" / "reference" / "cli-reference.md",
    ROOT / "docs" / "reference" / "compatibility-contract.md",
    ROOT / "docs" / "reference" / "compatibility-matrix.md",
    ROOT / "docs" / "reference" / "installed-skill-integrity.md",
    ROOT / "docs" / "reference" / "registry-refresh-policy.md",
    ROOT / "docs" / "reference" / "metadata-schema.md",
    ROOT / "docs" / "reference" / "distribution-manifests.md",
    ROOT / "docs" / "reference" / "promotion-policy.md",
    ROOT / "docs" / "reference" / "policy-packs.md",
    ROOT / "docs" / "reference" / "multi-registry.md",
]


def _parse_front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 3 and lines[0].strip() == "---", f"missing front matter start in {path}"
    metadata: dict[str, str] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return metadata
        assert ":" in stripped, f"invalid front matter line in {path}: {line!r}"
        key, value = stripped.split(":", 1)
        metadata[key.strip()] = value.strip()
    raise AssertionError(f"missing front matter end marker in {path}")


@pytest.mark.parametrize("path", TARGETS, ids=lambda p: p.name)
def test_reference_doc_exists(path: Path) -> None:
    assert path.exists(), f"missing expected maintained doc: {path}"


@pytest.mark.parametrize("path", TARGETS, ids=lambda p: p.name)
def test_reference_doc_has_required_metadata(path: Path) -> None:
    metadata = _parse_front_matter(path)
    for field in REQUIRED_FIELDS:
        assert metadata.get(field), f"missing required metadata field {field!r} in {path}"
