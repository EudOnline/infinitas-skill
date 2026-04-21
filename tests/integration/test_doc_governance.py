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
    fake_platform = fake_docs / "platform-contracts"

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
    )
    _write(
        fake_platform / "README.md",
        "---\n"
        "audience: automation\n"
        "owner: maintainers\n"
        "source_of_truth: legacy platform landing\n"
        "last_reviewed: 2026-04-21\n"
        "status: legacy\n"
        "---\n\n"
        "# Platform contracts\n\n"
        "- [OpenClaw](openclaw.md)\n",
    )
    _write(
        fake_platform / "openclaw.md",
        "---\n"
        "audience: automation\n"
        "owner: maintainers\n"
        "source_of_truth: legacy platform annex\n"
        "last_reviewed: 2026-04-21\n"
        "status: legacy\n"
        "---\n\n"
        "# OpenClaw\n",
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
    monkeypatch.setattr(
        module, "LEGACY_SECTION_LANDINGS", {"platform-contracts": fake_platform / "README.md"}
    )
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


def test_legacy_ai_landing_is_removed_from_docs_entrypoints() -> None:
    docs_readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert "ai/README.md" not in docs_readme
    assert "platform-contracts/README.md" in docs_readme


def test_legacy_ai_annex_is_removed_from_the_docs_tree() -> None:
    assert not (ROOT / "docs" / "ai").exists()
