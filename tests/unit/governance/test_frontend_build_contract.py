from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_css_build_uses_ignored_intermediate_file() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    purge_script = (ROOT / "scripts" / "purgecss-run.js").read_text(encoding="utf-8")

    assert "build/static/input.purged.css" in package["scripts"]["build:css"]
    assert "build/static/input.purged.css" in purge_script
    assert "server/static/css/.input.purged.css" not in package["scripts"]["build:css"]
    assert "server/static/css/.input.purged.css" not in purge_script


def test_package_metadata_matches_python_release_and_root_license() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    license_heading = (ROOT / "LICENSE").read_text(encoding="utf-8").splitlines()[0]

    assert package["version"] == pyproject["project"]["version"] == "0.1.0"
    assert lock["version"] == lock["packages"][""]["version"] == "0.1.0"
    assert package["license"] == pyproject["project"]["license"] == "MIT"
    assert license_heading == "MIT License"


def test_validate_workflow_installs_playwright_browser_runtime() -> None:
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")

    install = ".venv/bin/playwright install --with-deps chromium"
    verification = "run: scripts/check-all.sh"

    assert install in workflow
    assert verification in workflow
    assert workflow.index(install) < workflow.index(verification)
