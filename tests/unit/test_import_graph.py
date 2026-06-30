"""Verify that src/infinitas_skill/server/ has no module-level imports from server.*

This test ensures the bidirectional dependency is fully resolved.
It should be run after Phase 1 is complete.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVER_LIB_DIR = ROOT / "src" / "infinitas_skill" / "server"


def _collect_module_level_server_imports(directory: Path) -> list[tuple[str, int, str]]:
    """Parse all .py files and find module-level 'from server.' imports."""
    violations: list[tuple[str, int, str]] = []
    for py_file in sorted(directory.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue
        rel = py_file.relative_to(ROOT)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("server")
            ):
                # Only flag module-level imports (col_offset == 0)
                if node.col_offset == 0:
                    violations.append((str(rel), node.lineno, f"from {node.module} import ..."))
    return violations


class TestNoModuleLevelServerImports:
    def test_no_upward_imports_from_library(self):
        """src/infinitas_skill/server/ must not have module-level imports from server.*"""
        if not SERVER_LIB_DIR.exists():
            pytest.skip("Library server directory not found")

        violations = _collect_module_level_server_imports(SERVER_LIB_DIR)
        if violations:
            lines = [f"  {path}:{line} — {stmt}" for path, line, stmt in violations]
            msg = (
                f"Found {len(violations)} module-level upward import(s) "
                "in src/infinitas_skill/server/:\n" + "\n".join(lines)
            )
            pytest.fail(msg)
