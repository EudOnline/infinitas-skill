from __future__ import annotations

from infinitas_skill.install.service import constraint_display, normalize_meta_dependencies


def test_package_exports_registry_integrity_helpers() -> None:
    assert callable(constraint_display)
    assert callable(normalize_meta_dependencies)
