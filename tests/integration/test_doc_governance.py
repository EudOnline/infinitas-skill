from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_doc_governance_module():
    path = ROOT / "scripts" / "test-doc-governance.py"
    spec = importlib.util.spec_from_file_location("doc_governance_script", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_doc_governance_rejects_retired_cli_wrappers_in_maintained_ops_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_doc_governance_module()

    fake_root = tmp_path
    fake_docs = fake_root / "docs"
    fake_ops = fake_docs / "ops"
    fake_ai = fake_docs / "ai"

    _write(
        fake_root / "README.md",
        "# repo\n\n## Maintained surfaces\n\npackage-owned:\nruntime-owned:\nautomation-owned:\n",
    )
    _write(
        fake_docs / "README.md",
        "---\n"
        "audience: contributors\n"
        "owner: maintainers\n"
        "source_of_truth: docs landing\n"
        "last_reviewed: 2026-04-05\n"
        "status: maintained\n"
        "---\n\n"
        "# Docs\n\n"
        "- [Ops](ops/README.md)\n"
        "- [Legacy AI](ai/README.md)\n",
    )
    _write(
        fake_ai / "README.md",
        "---\n"
        "audience: automation\n"
        "owner: maintainers\n"
        "source_of_truth: legacy ai landing\n"
        "last_reviewed: 2026-04-21\n"
        "status: legacy\n"
        "---\n\n"
        "# AI\n\n"
        "- [Protocol](discovery.md)\n",
    )
    _write(
        fake_ai / "discovery.md",
        "---\n"
        "audience: automation\n"
        "owner: maintainers\n"
        "source_of_truth: legacy ai annex\n"
        "last_reviewed: 2026-04-21\n"
        "status: legacy\n"
        "---\n\n"
        "# Discovery\n",
    )
    _write(
        fake_ops / "README.md",
        "---\n"
        "audience: operators\n"
        "owner: maintainers\n"
        "source_of_truth: ops landing\n"
        "last_reviewed: 2026-04-05\n"
        "status: maintained\n"
        "---\n\n"
        "# Ops\n\n"
        "- [Release scorecard](2026-04-01-release-readiness-scorecard.md)\n",
    )
    _write(
        fake_ops / "2026-04-01-release-readiness-scorecard.md",
        "---\n"
        "audience: operators\n"
        "owner: maintainers\n"
        "source_of_truth: scorecard\n"
        "last_reviewed: 2026-04-05\n"
        "status: maintained\n"
        "---\n\n"
        "# Scorecard\n\n"
        "`python3 scripts/test-infinitas-cli-policy.py`\n",
    )

    monkeypatch.setattr(module, "ROOT", fake_root)
    monkeypatch.setattr(module, "DOCS_ROOT", fake_docs)
    monkeypatch.setattr(module, "SECTION_LANDINGS", {"ops": fake_ops / "README.md"})
    monkeypatch.setattr(module, "LEGACY_SECTION_LANDINGS", {"ai": fake_ai / "README.md"})
    monkeypatch.setattr(
        module, "GLOBAL_INDEXES", [fake_root / "README.md", fake_docs / "README.md"]
    )
    monkeypatch.setattr(module, "LEGACY_ROOT_ALLOWLIST", {"README.md"})

    with pytest.raises(SystemExit):
        module.main()

    captured = capsys.readouterr()
    assert "scripts/test-infinitas-cli-policy.py" in captured.err


def test_openclaw_runtime_docs_are_canonical_entrypoints() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    compatibility_contract = (ROOT / "docs" / "reference" / "compatibility-contract.md").read_text(
        encoding="utf-8"
    )
    compatibility_matrix = (ROOT / "docs" / "reference" / "compatibility-matrix.md").read_text(
        encoding="utf-8"
    )

    adr_path = ROOT / "docs" / "adr" / "0003-openclaw-runtime-canonical.md"
    runtime_contract_path = ROOT / "docs" / "reference" / "openclaw-runtime-contract.md"

    assert adr_path.exists()
    assert runtime_contract_path.exists()
    assert "OpenClaw is now the canonical agent runtime" in readme
    assert "`agent_compatible` as legacy migration metadata" in compatibility_contract
    assert "legacy and transitional" in compatibility_matrix


def test_openclaw_canonical_runtime_docs_preserve_backend_control_plane_boundary() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    reference_readme = (ROOT / "docs" / "reference" / "README.md").read_text(encoding="utf-8")
    compatibility_matrix = (ROOT / "docs" / "reference" / "compatibility-matrix.md").read_text(
        encoding="utf-8"
    )

    assert "registry/release/install backend remains the durable control plane" in readme
    assert "adr/0003-openclaw-runtime-canonical.md" in docs_readme
    assert "reference/openclaw-runtime-contract.md" in docs_readme
    assert "openclaw-runtime-contract.md" in reference_readme
    assert "legacy and transitional" in compatibility_matrix


def test_legacy_doc_surfaces_are_explicitly_indexed_and_metadata_tagged() -> None:
    docs_readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    expected_landings = [
        ROOT / "docs" / "ai" / "README.md",
        ROOT / "docs" / "platform-contracts" / "README.md",
    ]
    expected_legacy_docs = [
        ROOT / "docs" / "ai" / "README.md",
        ROOT / "docs" / "ai" / "memory.md",
        ROOT / "docs" / "ai" / "workflow-drills.md",
        ROOT / "docs" / "platform-contracts" / "README.md",
        ROOT / "docs" / "platform-contracts" / "openclaw.md",
        ROOT / "docs" / "project-closeout.md",
        ROOT / "docs" / "registry-snapshot-mirrors.md",
        ROOT / "docs" / "release-strategy.md",
    ]

    for landing in expected_landings:
        assert landing.exists(), f"expected legacy landing page to exist: {landing}"
        assert landing.name in docs_readme, (
            f"expected docs/README.md to index legacy landing page {landing.name}"
        )

    for path in expected_legacy_docs:
        assert path.exists(), f"expected legacy doc to exist: {path}"
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert len(lines) >= 3 and lines[0].strip() == "---", (
            f"expected explicit front matter on legacy doc {path}"
        )
        metadata = {}
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break
            key, value = stripped.split(":", 1)
            metadata[key.strip()] = value.strip()
        assert metadata.get("status") == "legacy", (
            f"expected legacy doc {path} to be tagged with status: legacy"
        )
        for field in ["audience", "owner", "source_of_truth", "last_reviewed"]:
            assert metadata.get(field), f"expected legacy doc {path} to declare {field}"
