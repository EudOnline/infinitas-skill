"""Repository skill lifecycle operations used by the release CLI."""

from __future__ import annotations

import difflib
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from infinitas_skill.policy.reviews import resolve_skill
from infinitas_skill.skills.openclaw import slugify

_TEMPLATES = {
    "basic": "basic-skill",
    "scripted": "scripted-skill",
    "reference-heavy": "reference-heavy-skill",
}
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def scaffold_skill(
    *,
    root: str | Path,
    requested_name: str,
    template: str = "basic",
    target_root: str = "skills/incubating",
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    publisher_raw, separator, name_raw = requested_name.partition("/")
    publisher = slugify(publisher_raw) if separator else ""
    name = slugify(name_raw if separator else publisher_raw)
    if not name or (separator and not publisher):
        raise ValueError(f"invalid skill identity: {requested_name}")
    template_dir_name = _TEMPLATES.get(template)
    if template_dir_name is None:
        raise ValueError(f"unknown template: {template}")
    source = repo_root / "templates" / template_dir_name
    target = (repo_root / target_root / name).resolve()
    if target.exists():
        raise ValueError(f"target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)

    skill_md = target / "SKILL.md"
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if not replaced and line.startswith("name: "):
            lines[index] = f"name: {name}"
            replaced = True
    skill_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    meta_path = target / "_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["name"] = name
    if publisher:
        meta["publisher"] = publisher
        meta["qualified_name"] = f"{publisher}/{name}"
    _write_json(meta_path, meta)
    return {
        "ok": True,
        "target_dir": str(target),
        "name": name,
        "publisher": publisher or None,
        "qualified_name": meta.get("qualified_name") or name,
    }


def _next_version(current: str, bump_kind: str, set_version: str | None) -> str:
    if set_version:
        if not _SEMVER_RE.match(set_version):
            raise ValueError(f"invalid target version: {set_version}")
        return set_version
    match = _SEMVER_RE.match(current)
    if not match:
        raise ValueError(f"invalid current version: {current}")
    major, minor, patch = (int(value) for value in match.groups())
    if bump_kind == "major":
        return f"{major + 1}.0.0"
    if bump_kind == "minor":
        return f"{major}.{minor + 1}.0"
    if bump_kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"invalid bump kind: {bump_kind}")


def bump_skill_version(
    skill_dir: str | Path,
    *,
    bump_kind: str = "patch",
    set_version: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    path = Path(skill_dir).resolve()
    meta_path = path / "_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    current = str(meta["version"])
    new_version = _next_version(current, bump_kind, set_version)
    meta["version"] = new_version
    _write_json(meta_path, meta)

    changelog_path = path / "CHANGELOG.md"
    existing = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
    entry = [f"## {new_version} - {date.today().isoformat()}", ""]
    entry.extend(f"- {note}" for note in (notes or ["Describe the changes in this release."]))
    entry_text = "\n".join(entry) + "\n\n"
    if existing.startswith("# Changelog"):
        remainder = existing.removeprefix("# Changelog").lstrip("\n")
        updated = f"# Changelog\n\n{entry_text}{remainder}"
    else:
        updated = f"# Changelog\n\n{entry_text}{existing}"
    changelog_path.write_text(updated, encoding="utf-8")
    return {
        "ok": True,
        "skill_dir": str(path),
        "from_version": current,
        "to_version": new_version,
    }


def snapshot_active_skill(
    *, root: str | Path, skill_name: str, label: str | None = None
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    source = repo_root / "skills" / "active" / skill_name
    if not source.is_dir():
        raise ValueError(f"missing active skill: {skill_name}")
    meta = json.loads((source / "_meta.json").read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_label = slugify(label or "")
    suffix = f"-{safe_label}" if safe_label else ""
    target = (
        repo_root / "skills" / "archived" / f"{meta['name']}--v{meta['version']}--{stamp}{suffix}"
    )
    if target.exists():
        raise ValueError(f"snapshot already exists: {target}")
    shutil.copytree(source, target)
    snapshot_meta = dict(meta)
    snapshot_meta["status"] = "archived"
    snapshot_meta["snapshot_of"] = f"{meta['name']}@{meta['version']}"
    snapshot_meta["snapshot_created_at"] = stamp
    if label:
        snapshot_meta["snapshot_label"] = label
    _write_json(target / "_meta.json", snapshot_meta)
    return {"ok": True, "snapshot_dir": str(target), "snapshot_of": snapshot_meta["snapshot_of"]}


def lineage_diff(*, root: str | Path, skill: str, include_diff: bool = True) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    skill_dir = resolve_skill(repo_root, skill)
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    derived_from = meta.get("derived_from")
    payload: dict[str, Any] = {
        "ok": True,
        "skill": meta.get("qualified_name") or meta.get("name"),
        "version": meta.get("version"),
        "derived_from": derived_from,
        "diff": "",
    }
    if not isinstance(derived_from, str) or not derived_from:
        return payload
    ancestor_name = derived_from.split("@", 1)[0]
    ancestor = resolve_skill(repo_root, ancestor_name)
    payload["ancestor_dir"] = str(ancestor)
    if include_diff:
        left = (ancestor / "SKILL.md").read_text(encoding="utf-8").splitlines()
        right = (skill_dir / "SKILL.md").read_text(encoding="utf-8").splitlines()
        payload["diff"] = "\n".join(
            difflib.unified_diff(left, right, fromfile=str(ancestor), tofile=str(skill_dir))
        )
    return payload


__all__ = ["bump_skill_version", "lineage_diff", "scaffold_skill", "snapshot_active_skill"]
