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

    _write(
        fake_root / "README.md",
        "# repo\n\n"
        "## Maintained surfaces\n\n"
        "package-owned:\n"
        "runtime-owned:\n"
        "automation-owned:\n",
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
        "- [Ops](ops/README.md)\n",
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
    monkeypatch.setattr(module, "GLOBAL_INDEXES", [fake_root / "README.md", fake_docs / "README.md"])
    monkeypatch.setattr(module, "LEGACY_ROOT_ALLOWLIST", {"README.md"})

    with pytest.raises(SystemExit):
        module.main()

    captured = capsys.readouterr()
    assert "scripts/test-infinitas-cli-policy.py" in captured.err
