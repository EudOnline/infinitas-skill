from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "infinitas_skill.cli.main", *args],
        cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
        text=True,
        capture_output=True,
    )


def test_registry_sources_check_uses_package_cli() -> None:
    result = _run_cli(["registry", "sources", "check", "--json"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["registry_count"] >= 1


def test_registry_sources_list_reports_default_registry() -> None:
    result = _run_cli(["registry", "sources", "list", "--json"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["default_registry"] == "self"
    assert any(item["name"] == "self" for item in payload["registries"])


def test_registry_sources_sync_handles_local_only_source() -> None:
    result = _run_cli(["registry", "sources", "sync", "self", "--json"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["registry"] == "self"
    assert payload["mode"] == "local-only"
    assert Path(payload["path"]) == ROOT


def test_registry_catalog_build_check_is_stable() -> None:
    result = _run_cli(["registry", "catalog", "build", "--check", "--json"])

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["changed"] == []
