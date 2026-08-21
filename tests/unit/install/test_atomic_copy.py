from __future__ import annotations

from pathlib import Path

from infinitas_skill.install import common
from infinitas_skill.install.common import _copy_skill_tree


def test_copy_skill_tree_replaces_existing_tree_without_leaving_staging(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "target" / "demo"
    source.mkdir()
    destination.mkdir(parents=True)
    (source / "new.txt").write_text("new", encoding="utf-8")
    (destination / "old.txt").write_text("old", encoding="utf-8")

    _copy_skill_tree(source_dir=str(source), dest_dir=str(destination))

    assert (destination / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (destination / "old.txt").exists()
    assert not list(destination.parent.glob(".demo.install-*"))


def test_apply_plan_restores_previous_tree_when_manifest_update_fails(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "target" / "demo"
    source.mkdir()
    destination.mkdir(parents=True)
    (source / "new.txt").write_text("new", encoding="utf-8")
    (destination / "old.txt").write_text("old", encoding="utf-8")
    monkeypatch.setattr(common, "_check_skill_dir", lambda **_kwargs: (0, None))
    monkeypatch.setattr(
        common,
        "_update_install_manifest_entry",
        lambda **_kwargs: (1, {"error_code": "fixture-failure"}),
    )

    code, applied, payload = common._apply_plan(
        repo_root=tmp_path,
        target_dir=str(tmp_path / "target"),
        plan={
            "steps": [
                {
                    "name": "demo",
                    "root": True,
                    "needs_apply": True,
                    "action": "upgrade",
                    "version": "2.0.0",
                }
            ]
        },
        root_materialized={"materialized_path": str(source)},
        root_resolved={"registry_name": "public"},
        cleanup_dirs=[],
    )

    assert (code, applied, payload) == (1, 0, {"error_code": "fixture-failure"})
    assert (destination / "old.txt").read_text(encoding="utf-8") == "old"
    assert not (destination / "new.txt").exists()
    assert not list(destination.parent.glob(".demo.install-*"))
