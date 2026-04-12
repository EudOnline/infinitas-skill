from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK_ALL_PATH = ROOT / "scripts" / "check-all.sh"
VALIDATE_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "validate.yml"
PACKAGE_JSON_PATH = ROOT / "package.json"

MAX_LINES = {
    "server/app.py": 80,
    "src/infinitas_skill/server/ops.py": 550,
    "src/infinitas_skill/install/service.py": 650,
    "src/infinitas_skill/release/service.py": 650,
    "server/ui/lifecycle.py": 500,
}
MAX_TOP_LEVEL_SCRIPT_FILES = 221


def test_maintained_modules_stay_under_line_budgets() -> None:
    for rel, budget in MAX_LINES.items():
        line_count = len((ROOT / rel).read_text(encoding="utf-8").splitlines())
        assert line_count <= budget, f"{rel} exceeded budget: {line_count} > {budget}"


def test_top_level_script_count_stays_within_reset_ceiling() -> None:
    script_files = sorted(path for path in (ROOT / "scripts").iterdir() if path.is_file())
    assert len(script_files) <= MAX_TOP_LEVEL_SCRIPT_FILES, (
        "top-level script count exceeded reset ceiling: "
        f"{len(script_files)} > {MAX_TOP_LEVEL_SCRIPT_FILES}"
    )


def test_fast_path_wires_maintainability_budget_check() -> None:
    check_all = CHECK_ALL_PATH.read_text(encoding="utf-8")
    workflow = VALIDATE_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "tests/integration/test_maintainability_budgets.py" in check_all
    assert "scripts/check-all.sh" in workflow


def test_validate_workflow_covers_frontend_build_contract() -> None:
    workflow = VALIDATE_WORKFLOW_PATH.read_text(encoding="utf-8")
    package = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
    test_script = (package.get("scripts") or {}).get("test")

    assert "actions/setup-node" in workflow
    assert "npm ci" in workflow
    assert "npm run build" in workflow
    assert isinstance(test_script, str) and "no test specified" not in test_script
