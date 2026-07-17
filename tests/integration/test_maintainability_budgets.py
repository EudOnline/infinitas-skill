from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK_ALL_PATH = ROOT / "scripts" / "check-all.sh"
VALIDATE_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "validate.yml"
PACKAGE_JSON_PATH = ROOT / "package.json"
RUFF_BUDGET_CONFIG_PATH = ROOT / "config" / "ruff-budgets.json"
RUFF_BUDGET_SCRIPT_PATH = ROOT / "scripts" / "check-ruff-budgets.py"
PRODUCTION_ROOTS = (ROOT / "server", ROOT / "src" / "infinitas_skill")
MAX_PRODUCTION_MODULE_LINES = 600
MAX_PRODUCTION_FUNCTION_LINES = 100
MAX_PRODUCTION_FUNCTION_PARAMETERS = 13
MAX_PYTHON_BRANCH_SCORE = 30
MAX_CSS_INPUT_LINES = 1_000
MAX_JAVASCRIPT_MODULE_LINES = 350
MAX_JAVASCRIPT_FUNCTION_LINES = 80
MAX_JAVASCRIPT_BRANCH_SCORE = 25
MAX_TOP_LEVEL_SCRIPT_FILES = 4
TOP_LEVEL_SCRIPT_ALLOWLIST = {
    "build-asset-hashes.js",
    "check-all.sh",
    "generate-openapi.py",
    "purgecss-run.js",
}


def _production_python_files() -> list[Path]:
    return [path for root in PRODUCTION_ROOTS for path in sorted(root.rglob("*.py"))]


def test_production_modules_stay_under_line_ceiling() -> None:
    violations = []
    for path in _production_python_files():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_PRODUCTION_MODULE_LINES:
            violations.append(f"{path.relative_to(ROOT)}: {line_count}")
    assert not violations, "production modules exceed 600 lines:\n" + "\n".join(violations)


def test_production_functions_stay_under_line_ceiling() -> None:
    violations = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            line_count = (node.end_lineno or node.lineno) - node.lineno + 1
            if line_count > MAX_PRODUCTION_FUNCTION_LINES:
                violations.append(
                    f"{path.relative_to(ROOT)}:{node.lineno} {node.name}: {line_count}"
                )
    assert not violations, "production functions exceed 100 lines:\n" + "\n".join(violations)


def _python_parameter_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    return (
        len(node.args.posonlyargs)
        + len(node.args.args)
        + len(node.args.kwonlyargs)
        + int(node.args.vararg is not None)
        + int(node.args.kwarg is not None)
    )


def _python_branch_score(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    score = 1
    branch_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.IfExp,
        ast.ExceptHandler,
        ast.comprehension,
        ast.Match,
    )
    for child in ast.walk(node):
        if isinstance(child, branch_nodes):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(0, len(child.values) - 1)
    return score


def test_production_function_parameters_stay_under_ceiling() -> None:
    violations = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            parameter_count = _python_parameter_count(node)
            if parameter_count > MAX_PRODUCTION_FUNCTION_PARAMETERS:
                violations.append(
                    f"{path.relative_to(ROOT)}:{node.lineno} {node.name}: {parameter_count}"
                )
    assert not violations, "production functions exceed 13 parameters:\n" + "\n".join(violations)


def test_python_branch_scores_stay_under_ceiling() -> None:
    violations = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            score = _python_branch_score(node)
            if score > MAX_PYTHON_BRANCH_SCORE:
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}: {score}")
    assert not violations, "Python branch scores exceed 30:\n" + "\n".join(violations)


def test_css_input_stays_under_line_ceiling() -> None:
    css_path = ROOT / "server" / "static" / "css" / "input.css"
    line_count = len(css_path.read_text(encoding="utf-8").splitlines())
    assert line_count <= MAX_CSS_INPUT_LINES, f"CSS input exceeded ceiling: {line_count} > 1000"


def _javascript_files() -> list[Path]:
    static_root = ROOT / "server" / "static" / "js"
    return sorted(static_root.glob("*.js")) + sorted((static_root / "modules").glob("*.js"))


def _matching_brace_line(lines: list[str], start_line: int) -> int | None:
    depth = 0
    started = False
    quote: str | None = None
    escaped = False
    for line_index in range(start_line, len(lines)):
        for character in lines[line_index]:
            if escaped:
                escaped = False
                continue
            if character == "\\" and quote:
                escaped = True
                continue
            if quote:
                if character == quote:
                    quote = None
                continue
            if character in {"'", '"', "`"}:
                quote = character
            elif character == "{":
                depth += 1
                started = True
            elif character == "}" and started:
                depth -= 1
                if depth == 0:
                    return line_index
    return None


def _javascript_function_starts(lines: list[str]) -> list[tuple[int, str]]:
    patterns = [
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
        re.compile(r"^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^;]*\)\s*\{"),
        re.compile(r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=.*=>\s*\{"),
    ]
    starts: list[tuple[int, str]] = []
    for line_index, line in enumerate(lines):
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                starts.append((line_index, match.group(1)))
                break
    return starts


def test_javascript_modules_stay_under_line_ceiling() -> None:
    violations = []
    for path in _javascript_files():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_JAVASCRIPT_MODULE_LINES:
            violations.append(f"{path.relative_to(ROOT)}: {line_count}")
    assert not violations, "JavaScript modules exceed 350 lines:\n" + "\n".join(violations)


def test_javascript_functions_stay_under_line_ceiling() -> None:
    violations = []
    for path in _javascript_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for start_line, name in _javascript_function_starts(lines):
            end_line = _matching_brace_line(lines, start_line)
            if end_line is None:
                continue
            line_count = end_line - start_line + 1
            if line_count > MAX_JAVASCRIPT_FUNCTION_LINES:
                violations.append(f"{path.relative_to(ROOT)}:{start_line + 1} {name}: {line_count}")
    assert not violations, "JavaScript functions exceed 80 lines:\n" + "\n".join(violations)


def test_javascript_branch_scores_stay_under_ceiling() -> None:
    branch_pattern = re.compile(r"\b(?:if|for|while|catch|case)\b|&&|\|\||\?(?![.?])")
    violations = []
    for path in _javascript_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for start_line, name in _javascript_function_starts(lines):
            end_line = _matching_brace_line(lines, start_line)
            if end_line is None:
                continue
            body = "\n".join(lines[start_line : end_line + 1])
            score = 1 + len(branch_pattern.findall(body))
            if score > MAX_JAVASCRIPT_BRANCH_SCORE:
                violations.append(f"{path.relative_to(ROOT)}:{start_line + 1} {name}: {score}")
    assert not violations, "JavaScript branch scores exceed 25:\n" + "\n".join(violations)


def test_top_level_script_count_stays_within_reset_ceiling() -> None:
    script_files = sorted(path for path in (ROOT / "scripts").iterdir() if path.is_file())
    assert len(script_files) <= MAX_TOP_LEVEL_SCRIPT_FILES, (
        "top-level script count exceeded reset ceiling: "
        f"{len(script_files)} > {MAX_TOP_LEVEL_SCRIPT_FILES}"
    )


def test_top_level_scripts_match_build_allowlist() -> None:
    script_files = {path.name for path in (ROOT / "scripts").iterdir() if path.is_file()}
    assert script_files == TOP_LEVEL_SCRIPT_ALLOWLIST


def test_check_all_runs_direct_quality_gates() -> None:
    check_all = CHECK_ALL_PATH.read_text(encoding="utf-8")
    workflow = VALIDATE_WORKFLOW_PATH.read_text(encoding="utf-8")
    for command in (
        "ruff check .",
        "ruff format --check .",
        "mypy src/infinitas_skill server",
        (
            "pytest tests/unit tests/integration tests/security tests/performance "
            "--cov-fail-under=64"
        ),
        "pytest tests/e2e",
        "pytest tests/integration/test_alembic_metadata.py -q --override-ini=addopts=",
        "scripts/generate-openapi.py --check",
        "pip-audit",
        "npm audit --registry=https://registry.npmjs.org --audit-level=high",
        "npm run build",
    ):
        assert command in check_all
    assert "scripts/check-all.sh" in workflow


def test_container_publication_depends_on_the_single_release_gate() -> None:
    workflow = VALIDATE_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "tags: ['v*']" in workflow
    assert workflow.count("scripts/check-all.sh") == 1
    assert "build-container:" in workflow
    assert "needs: [validate, python-314-archive-preview]" in workflow
    assert workflow.index("scripts/check-all.sh") < workflow.index("docker/build-push-action")
    assert "make ci-fast" not in workflow
    assert "tests/unit -q --override-ini=addopts=" not in workflow


def test_validate_workflow_previews_archive_extraction_on_python_314() -> None:
    workflow = VALIDATE_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "python-314-archive-preview:" in workflow
    assert "python-version: '3.14'" in workflow
    assert "tests/unit/install/test_distribution_materialization.py" in workflow


def test_validate_workflow_covers_frontend_build_contract() -> None:
    workflow = VALIDATE_WORKFLOW_PATH.read_text(encoding="utf-8")
    package = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
    test_script = (package.get("scripts") or {}).get("test")

    assert "actions/setup-node" in workflow
    assert "npm ci" in workflow
    assert "scripts/check-all.sh" in workflow
    assert isinstance(test_script, str) and "no test specified" not in test_script


def test_ruff_debt_budget_files_are_deleted() -> None:
    assert not RUFF_BUDGET_CONFIG_PATH.exists()
    assert not RUFF_BUDGET_SCRIPT_PATH.exists()
