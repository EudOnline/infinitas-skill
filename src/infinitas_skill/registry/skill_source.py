"""Normalize agent skill directories into validated hosted bundles."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from infinitas_skill.install.distribution import deterministic_bundle
from infinitas_skill.install.skill_validation import validate_installable_skill_dir

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_IGNORED_NAMES = {".DS_Store", ".git", "__pycache__"}


class SkillSourceError(ValueError):
    """Raised when a local agent skill cannot be prepared for hosting."""


@dataclass(frozen=True)
class StagedSkillSource:
    source_dir: Path
    skill_dir: Path
    slug: str
    publisher: str
    qualified_name: str
    version: str
    generated_files: tuple[str, ...]
    metadata: dict[str, Any]


def _frontmatter_value(skill_md: Path, field: str) -> str | None:
    prefix = f"{field}:"
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1].strip()
        return value or None
    return None


def _load_existing_metadata(source_dir: Path) -> dict[str, Any]:
    path = source_dir / "_meta.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillSourceError(f"could not read existing _meta.json: {exc}") from exc
    if not isinstance(payload, dict):
        raise SkillSourceError("existing _meta.json must contain an object")
    return payload


def _assert_safe_source(source_dir: Path) -> None:
    if not source_dir.is_dir():
        raise SkillSourceError(f"skill source directory does not exist: {source_dir}")
    if not (source_dir / "SKILL.md").is_file():
        raise SkillSourceError(f"skill source has no SKILL.md: {source_dir}")
    symlinks = [path for path in source_dir.rglob("*") if path.is_symlink()]
    if symlinks:
        relative = ", ".join(str(path.relative_to(source_dir)) for path in symlinks[:5])
        raise SkillSourceError(f"skill sources with symbolic links are not supported: {relative}")


def _copy_source(source_dir: Path, destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in _IGNORED_NAMES}

    try:
        shutil.copytree(source_dir, destination, ignore=ignore)
    except OSError as exc:
        raise SkillSourceError(f"could not stage skill source: {exc}") from exc


def _normalized_metadata(
    existing: dict[str, Any],
    *,
    slug: str,
    publisher: str,
    version: str,
    description: str,
    review_state: str,
    risk_level: str,
) -> dict[str, Any]:
    metadata = dict(existing)
    metadata.update(
        {
            "schema_version": 1,
            "name": slug,
            "publisher": publisher,
            "qualified_name": f"{publisher}/{slug}",
            "version": version,
            "status": "active",
            "summary": str(existing.get("summary") or description),
            "owner": publisher,
            "owners": [publisher],
            "author": str(existing.get("author") or publisher),
            "maintainers": [publisher],
            "agent_compatible": list(existing.get("agent_compatible") or ["codex", "openclaw"]),
            "review_state": str(existing.get("review_state") or review_state),
            "risk_level": str(existing.get("risk_level") or risk_level),
            "distribution": {"installable": True, "channel": "hosted"},
            "entrypoints": {"skill_md": "SKILL.md"},
            "tests": {"smoke": "tests/smoke.md"},
        }
    )
    metadata.setdefault("tags", ["hosted"])
    metadata.setdefault("maturity", "beta")
    metadata.setdefault("quality_score", 70)
    metadata.setdefault("capabilities", ["agent-skill"])
    metadata.setdefault("use_when", [description])
    metadata.setdefault("avoid_when", ["The skill does not match the requested task"])
    metadata.setdefault("runtime_assumptions", ["A compatible agent runtime is available"])
    metadata.setdefault("requires", {"tools": [], "bins": [], "env": []})
    return metadata


def _write_generated_files(
    skill_dir: Path,
    *,
    metadata: dict[str, Any],
    version: str,
) -> tuple[str, ...]:
    generated: list[str] = ["_meta.json"]
    (skill_dir / "_meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    changelog = skill_dir / "CHANGELOG.md"
    if not changelog.exists():
        changelog.write_text(
            f"# Changelog\n\n## {version}\n\n- Initial hosted snapshot.\n",
            encoding="utf-8",
        )
        generated.append("CHANGELOG.md")
    smoke = skill_dir / "tests" / "smoke.md"
    if not smoke.exists():
        smoke.parent.mkdir(parents=True, exist_ok=True)
        smoke.write_text(
            "# Smoke Test\n\n"
            "Load the skill and confirm its instructions match the requested task.\n",
            encoding="utf-8",
        )
        generated.append("tests/smoke.md")
    return tuple(sorted(generated))


def stage_skill_source(
    source_dir: str | Path,
    staging_root: str | Path,
    *,
    publisher: str,
    version: str,
    slug: str | None = None,
    review_state: str = "draft",
    risk_level: str = "medium",
) -> StagedSkillSource:
    """Copy and normalize an agent skill without mutating its source directory."""
    source = Path(source_dir).expanduser().resolve()
    staging = Path(staging_root).expanduser().resolve()
    _assert_safe_source(source)
    skill_md = source / "SKILL.md"
    resolved_slug = slug or _frontmatter_value(skill_md, "name") or source.name
    if not _SLUG_RE.fullmatch(resolved_slug):
        raise SkillSourceError(f"invalid hosted skill slug: {resolved_slug!r}")
    if not _SLUG_RE.fullmatch(publisher):
        raise SkillSourceError(f"invalid publisher slug: {publisher!r}")
    description = _frontmatter_value(skill_md, "description")
    if not description:
        raise SkillSourceError("SKILL.md must declare a description")
    destination = staging / "active" / resolved_slug
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise SkillSourceError(f"staging destination already exists: {destination}")
    _copy_source(source, destination)
    staged_skill_md = destination / "SKILL.md"
    original_name = _frontmatter_value(staged_skill_md, "name")
    if original_name != resolved_slug:
        text = staged_skill_md.read_text(encoding="utf-8")
        text = re.sub(
            rf"(?m)^name:\s*{re.escape(original_name or '')}\s*$",
            f"name: {resolved_slug}",
            text,
            count=1,
        )
        staged_skill_md.write_text(text, encoding="utf-8")
    metadata = _normalized_metadata(
        _load_existing_metadata(source),
        slug=resolved_slug,
        publisher=publisher,
        version=version,
        description=description,
        review_state=review_state,
        risk_level=risk_level,
    )
    generated = _write_generated_files(destination, metadata=metadata, version=version)
    return StagedSkillSource(
        source_dir=source,
        skill_dir=destination,
        slug=resolved_slug,
        publisher=publisher,
        qualified_name=f"{publisher}/{resolved_slug}",
        version=version,
        generated_files=generated,
        metadata=metadata,
    )


def build_skill_source_bundle(
    staged: StagedSkillSource,
    output_path: str | Path,
    *,
    repo_root: str | Path,
) -> Path:
    """Validate a staged source and create its deterministic hosted bundle."""
    validate_installable_skill_dir(staged.skill_dir, repo_root=repo_root)
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    deterministic_bundle(staged.skill_dir, output, root_dir=staged.slug)
    return output


__all__ = [
    "SkillSourceError",
    "StagedSkillSource",
    "build_skill_source_bundle",
    "stage_skill_source",
]
