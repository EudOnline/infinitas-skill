from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_dependency_lib():
    module_path = ROOT / "scripts" / "dependency_lib.py"
    spec = importlib.util.spec_from_file_location("test_dependency_lib_exports", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dependency_lib_still_exports_registry_integrity_helpers() -> None:
    module = _load_dependency_lib()

    assert callable(module.constraint_display)
    assert callable(module.normalize_meta_dependencies)
