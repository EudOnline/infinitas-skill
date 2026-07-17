from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.helpers.import_graph import build_import_graph, strongly_connected_components

ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_ROOTS = (ROOT / "server", ROOT / "src" / "infinitas_skill")
PENDING_CLEAN_RESET = pytest.mark.xfail(
    reason="final clean-architecture target is intentionally pending",
    strict=True,
)


def _python_files(*roots: Path) -> Iterator[Path]:
    for root in roots:
        yield from sorted(root.rglob("*.py"))


def _imports(path: Path) -> Iterator[ast.Import | ast.ImportFrom]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_import_graph_resolves_absolute_and_relative_imports(tmp_path: Path) -> None:
    package = tmp_path / "sample"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "alpha.py").write_text("from sample import beta\n", encoding="utf-8")
    (package / "beta.py").write_text("from . import gamma\n", encoding="utf-8")
    (package / "gamma.py").write_text("VALUE = 1\n", encoding="utf-8")

    graph = build_import_graph((package,))

    assert graph["sample.alpha"] == {"sample.beta"}
    assert graph["sample.beta"] == {"sample.gamma"}
    assert graph["sample.gamma"] == set()


def test_import_graph_reports_multi_module_cycles(tmp_path: Path) -> None:
    package = tmp_path / "sample"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "alpha.py").write_text("from sample import beta\n", encoding="utf-8")
    (package / "beta.py").write_text("from sample import alpha\n", encoding="utf-8")

    graph = build_import_graph((package,))

    assert ("sample.alpha", "sample.beta") in strongly_connected_components(graph)


def test_central_model_facade_is_deleted() -> None:
    assert not (ROOT / "server" / "models.py").exists()


def test_api_routers_are_owned_by_domains() -> None:
    assert not (ROOT / "server" / "api").exists()


def test_install_workflow_god_modules_are_deleted() -> None:
    install_root = ROOT / "src" / "infinitas_skill" / "install"
    assert not (install_root / "workflows.py").exists()
    assert not (install_root / "workflows_parsers.py").exists()

    violations: list[str] = []
    for path in _python_files(*PRODUCTION_ROOTS, ROOT / "tests", ROOT / "scripts"):
        for node in _imports(path):
            imported_modules = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
            )
            if any(
                name == "infinitas_skill.install.workflows"
                or name == "infinitas_skill.install.workflows_parsers"
                for name in imported_modules
            ):
                violations.append(f"{_relative(path)}:{node.lineno}")
    assert not violations, "legacy install workflow imports remain:\n" + "\n".join(violations)


def test_install_package_does_not_execute_repository_scripts() -> None:
    install_root = ROOT / "src" / "infinitas_skill" / "install"
    violations: list[str] = []
    for path in _python_files(install_root):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if '"scripts"' in line or "'scripts'" in line:
                violations.append(f"{_relative(path)}:{line_number}: {line.strip()}")
    assert not violations, "install package still executes repository scripts:\n" + "\n".join(
        violations
    )


def test_script_test_entrypoints_are_deleted() -> None:
    script_tests = sorted(_relative(path) for path in (ROOT / "scripts").glob("test-*.py"))
    assert not script_tests, "script test entrypoints remain:\n" + "\n".join(script_tests)


def test_alembic_has_one_initial_migration() -> None:
    migrations = sorted((ROOT / "alembic" / "versions").glob("*.py"))
    assert len(migrations) == 1, [path.name for path in migrations]


def test_production_code_does_not_import_server_models() -> None:
    violations: list[str] = []
    for path in _python_files(*PRODUCTION_ROOTS):
        for node in _imports(path):
            if isinstance(node, ast.ImportFrom) and node.module == "server.models":
                violations.append(f"{_relative(path)}:{node.lineno}")
            elif isinstance(node, ast.Import) and any(
                alias.name == "server.models" for alias in node.names
            ):
                violations.append(f"{_relative(path)}:{node.lineno}")
    assert not violations, "server.models imports remain:\n" + "\n".join(violations)


def test_domain_modules_do_not_import_ui() -> None:
    violations: list[str] = []
    for path in _python_files(ROOT / "server" / "modules"):
        for node in _imports(path):
            imported_modules = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
            )
            imports_ui = any(
                name == "server.ui" or name.startswith("server.ui.") for name in imported_modules
            )
            if imports_ui:
                violations.append(f"{_relative(path)}:{node.lineno}")
    assert not violations, "domain-to-UI imports found:\n" + "\n".join(violations)


def test_repository_has_no_sys_path_mutation() -> None:
    violations: list[str] = []
    roots = (*PRODUCTION_ROOTS, ROOT / "scripts", ROOT / "tests", ROOT / "alembic")
    for path in _python_files(*roots):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if (
                isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "sys"
                and owner.attr == "path"
                and node.func.attr in {"append", "insert"}
            ):
                violations.append(f"{_relative(path)}:{node.lineno}")
    assert not violations, "sys.path mutation remains:\n" + "\n".join(violations)


def test_domain_packages_do_not_eagerly_import_models_or_routers() -> None:
    violations: list[str] = []
    for path in sorted((ROOT / "server" / "modules").glob("*/__init__.py")):
        for node in _imports(path):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = {alias.name for alias in node.names}
                imports_boundary = module.endswith((".models", ".router")) or bool(
                    names & {"models", "router"}
                )
            else:
                imports_boundary = any(
                    alias.name.endswith((".models", ".router")) for alias in node.names
                )
            if imports_boundary:
                violations.append(f"{_relative(path)}:{node.lineno}")
    assert not violations, "eager domain package imports remain:\n" + "\n".join(violations)


def test_production_code_imports_domain_submodules_directly() -> None:
    violations: list[str] = []
    modules_root = ROOT / "server" / "modules"
    for path in _python_files(*PRODUCTION_ROOTS):
        for node in _imports(path):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            parts = node.module.split(".")
            if len(parts) != 3 or parts[:2] != ["server", "modules"]:
                continue
            domain_root = modules_root / parts[2]
            for alias in node.names:
                is_submodule = (domain_root / f"{alias.name}.py").is_file() or (
                    domain_root / alias.name / "__init__.py"
                ).is_file()
                if is_submodule:
                    violations.append(
                        f"{_relative(path)}:{node.lineno}: from {node.module} import {alias.name}"
                    )
    assert not violations, "domain package facade imports remain:\n" + "\n".join(violations)


def test_production_code_has_no_internal_compatibility_shims() -> None:
    pattern = re.compile(r"backward compatibility|backwards-compatible|re-export", re.IGNORECASE)
    violations: list[str] = []
    for path in _python_files(*PRODUCTION_ROOTS):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                violations.append(f"{_relative(path)}:{line_number}: {line.strip()}")
    assert not violations, "internal compatibility shims remain:\n" + "\n".join(violations)


def test_production_import_graph_has_no_cycles() -> None:
    graph = build_import_graph(PRODUCTION_ROOTS)
    cycles = [component for component in strongly_connected_components(graph) if len(component) > 1]
    formatted = "\n".join(" -> ".join(component) for component in cycles)
    assert not cycles, "production import cycles remain:\n" + formatted
