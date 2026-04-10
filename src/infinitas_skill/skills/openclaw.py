"""OpenClaw migration tooling and export-validation helpers.

This module intentionally owns bridge flows (import/export/validation) only.
Canonical OpenClaw runtime semantics live under ``infinitas_skill.openclaw``.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

from infinitas_skill.discovery.ai_index import validate_ai_index_payload
from infinitas_skill.install.distribution import materialize_distribution_source
from infinitas_skill.openclaw import load_openclaw_skill_contract

from .canonical import load_skill_source
from .render import load_platform_profile, render_skill

_TEXT_EXTENSIONS = {
    ".md",
    ".json",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".sh",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".html",
}
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


class OpenClawBridgeError(Exception):
    pass


OPENCLAW_BRIDGE_ROLE = "migration tooling"


def slugify(value: str) -> str:
    lowered = (value or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _strip_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def resolve_skill_dir(path_value: str) -> Path:
    candidate = Path(path_value).expanduser().resolve()
    if candidate.is_file() and candidate.name == "SKILL.md":
        candidate = candidate.parent
    if not candidate.is_dir():
        raise OpenClawBridgeError(f"source path is not a skill directory: {candidate}")
    if not (candidate / "SKILL.md").is_file():
        raise OpenClawBridgeError(f"missing SKILL.md in source directory: {candidate}")
    return candidate


def parse_skill_frontmatter(skill_md_path: Path) -> Dict[str, str]:
    content = skill_md_path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise OpenClawBridgeError(f"missing YAML frontmatter in {skill_md_path}")

    fields = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = _strip_quotes(value)

    if not fields.get("name"):
        raise OpenClawBridgeError(f"missing frontmatter name in {skill_md_path}")
    if not fields.get("description"):
        raise OpenClawBridgeError(f"missing frontmatter description in {skill_md_path}")
    return fields


def derive_registry_meta(
    frontmatter: Dict[str, str], owner: str, publisher: Optional[str] = None
) -> Dict[str, object]:
    owner_value = (owner or "").strip()
    if not owner_value:
        raise OpenClawBridgeError("owner must be non-empty")

    slug = slugify(frontmatter.get("name", ""))
    if not slug:
        raise OpenClawBridgeError("frontmatter name does not produce a valid registry slug")

    publisher_slug = slugify(publisher) if publisher else ""
    meta = {
        "name": slug,
        "version": "0.1.0",
        "status": "incubating",
        "summary": frontmatter.get("description", "").strip(),
        "owner": owner_value,
        "owners": [owner_value],
        "author": owner_value,
        "maintainers": [],
        "tags": [],
        "agent_compatible": ["openclaw", "claude-code", "codex"],
        "derived_from": None,
        "replaces": None,
        "visibility": "private",
        "review_state": "draft",
        "risk_level": "low",
        "requires": {
            "tools": [],
            "bins": [],
            "env": [],
        },
        "entrypoints": {
            "skill_md": "SKILL.md",
        },
        "tests": {
            "smoke": "tests/smoke.md",
        },
        "distribution": {
            "installable": True,
            "channel": "git",
        },
        "depends_on": [],
        "conflicts_with": [],
    }
    if publisher_slug:
        meta["publisher"] = publisher_slug
        meta["qualified_name"] = f"{publisher_slug}/{slug}"
    return meta


def scaffold_imported_skill(
    source_dir: Path, target_dir: Path, meta: Dict[str, object], force: bool = False
) -> Dict[str, object]:
    if target_dir.exists():
        if not force:
            raise OpenClawBridgeError(f"target already exists: {target_dir}")
        shutil.rmtree(target_dir)

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)

    (target_dir / "_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target_dir / "reviews.json").write_text(
        json.dumps({"version": 1, "requests": [], "entries": []}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    smoke_dir = target_dir / "tests"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    (smoke_dir / "smoke.md").write_text(
        "# Smoke test\n\n"
        "Validate that the imported OpenClaw skill still matches its original "
        "intent and required files.\n",
        encoding="utf-8",
    )

    copied_files = []
    for path in sorted(target_dir.rglob("*")):
        if path.is_file():
            copied_files.append(str(path.relative_to(target_dir)))

    return {
        "target_dir": str(target_dir),
        "files": copied_files,
        "meta": meta,
    }


def load_ai_index(root: Path) -> Dict[str, object]:
    index_path = root / "catalog" / "ai-index.json"
    if not index_path.exists():
        raise OpenClawBridgeError(f"missing AI index: {index_path}")
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    errors = validate_ai_index_payload(payload)
    if errors:
        raise OpenClawBridgeError("; ".join(errors))
    return payload


def select_ai_skill(ai_index: Dict[str, object], requested: str) -> Dict[str, object]:
    matches = []
    for skill in ai_index.get("skills", []):
        if requested == skill.get("qualified_name") or requested == skill.get("name"):
            matches.append(skill)

    if not matches:
        raise OpenClawBridgeError(f"no AI-index entry found for {requested}")

    exact = [skill for skill in matches if requested == skill.get("qualified_name")]
    if exact:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    choices = ", ".join(
        sorted(skill.get("qualified_name") or skill.get("name") or "?" for skill in matches)
    )
    raise OpenClawBridgeError(f"ambiguous skill name {requested}: {choices}")


def _is_probably_text_file(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_EXTENSIONS:
        return True
    try:
        data = path.read_bytes()
    except Exception:
        return False
    if b"\x00" in data[:8192]:
        return False
    return True


def validate_exported_openclaw_dir(
    skill_dir: Path, public_ready: bool = False
) -> Dict[str, object]:
    skill_dir = Path(skill_dir).resolve()
    errors = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        errors.append(f"missing SKILL.md: {skill_md}")
        return {"ok": False, "skill_dir": str(skill_dir), "public_ready": False, "errors": errors}
    try:
        frontmatter = parse_skill_frontmatter(skill_md)
    except OpenClawBridgeError as exc:
        errors.append(str(exc))
        return {"ok": False, "skill_dir": str(skill_dir), "public_ready": False, "errors": errors}

    requires = frontmatter.get("metadata.openclaw.requires")
    if not isinstance(requires, str) or not requires.strip():
        errors.append("missing metadata.openclaw.requires in SKILL.md frontmatter")

    if public_ready:
        license_value = frontmatter.get("metadata.openclaw.license")
        if license_value != "MIT-0":
            errors.append("public-ready exports require metadata.openclaw.license: MIT-0")

        total_size = 0
        for path in sorted(skill_dir.rglob("*")):
            if not path.is_file():
                continue
            total_size += path.stat().st_size
            if not _is_probably_text_file(path):
                errors.append(
                    f"public-ready exports must be text-only: {path.relative_to(skill_dir)}"
                )
        if total_size > 50 * 1024 * 1024:
            errors.append("public-ready exports must stay under 50MB")

    return {
        "ok": not errors,
        "skill_dir": str(skill_dir),
        "public_ready": public_ready and not errors,
        "errors": errors,
    }


def resolve_ai_release(
    root: Path, requested: str, requested_version: Optional[str] = None
) -> Tuple[Dict[str, object], str, Dict[str, object]]:
    ai_index = load_ai_index(root)
    policy = ai_index.get("install_policy") or {}
    if (
        policy.get("mode") != "immutable-only"
        or policy.get("direct_source_install_allowed") is not False
    ):
        raise OpenClawBridgeError(
            "AI install policy must be immutable-only with direct source installs disabled"
        )

    selected_skill = select_ai_skill(ai_index, requested)
    resolved_version = requested_version or selected_skill.get("default_install_version")
    versions = selected_skill.get("versions") or {}
    version_entry = versions.get(resolved_version)
    if not isinstance(version_entry, dict):
        raise OpenClawBridgeError(
            f"version {resolved_version!r} is not available for "
            f"{selected_skill.get('qualified_name') or selected_skill.get('name')}"
        )
    if version_entry.get("installable") is not True:
        raise OpenClawBridgeError(f"version {resolved_version!r} is not installable")

    required_fields = ["manifest_path", "bundle_path", "bundle_sha256", "attestation_path"]
    missing = [
        field
        for field in required_fields
        if not isinstance(version_entry.get(field), str) or not version_entry.get(field).strip()
    ]
    if missing:
        raise OpenClawBridgeError(f"missing distribution fields: {', '.join(missing)}")

    for field in ["manifest_path", "bundle_path", "attestation_path"]:
        full_path = (root / version_entry[field]).resolve()
        if not full_path.exists():
            raise OpenClawBridgeError(f"missing {field}: {version_entry[field]}")

    return selected_skill, resolved_version, version_entry


def export_release_to_directory(
    root: Path,
    manifest_path: Path,
    export_dir: Path,
    force: bool = False,
    public_ready: bool = False,
) -> Dict[str, object]:
    # Keep release export behavior for migration compatibility.
    export_dir = export_dir.resolve()
    if export_dir.exists():
        if not force:
            raise OpenClawBridgeError(f"target already exists: {export_dir}")
        shutil.rmtree(export_dir)
    export_dir.parent.mkdir(parents=True, exist_ok=True)

    materialized = materialize_distribution_source(
        {
            "source_type": "distribution-manifest",
            "distribution_manifest": str(manifest_path),
        },
        root=root,
    )
    source_dir = Path(materialized["materialized_path"]).resolve()
    cleanup_dir = materialized.get("cleanup_dir")
    try:
        profile = load_platform_profile(Path(root).resolve(), "openclaw")
        source = load_skill_source(source_dir)
        openclaw_contract = load_openclaw_skill_contract(source_dir)
        rendered = render_skill(
            source=source,
            platform="openclaw",
            out_dir=export_dir,
            profile=profile,
        )
        validation = validate_exported_openclaw_dir(export_dir, public_ready=public_ready)
    finally:
        if cleanup_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)

    return {
        "export_dir": str(export_dir),
        "files": rendered["files"],
        "migration_contract_source_mode": openclaw_contract["source_mode"],
        "public_ready": validation["public_ready"],
        "validation_errors": validation["errors"],
    }


__all__ = [
    "OPENCLAW_BRIDGE_ROLE",
    "OpenClawBridgeError",
    "slugify",
    "resolve_skill_dir",
    "parse_skill_frontmatter",
    "derive_registry_meta",
    "scaffold_imported_skill",
    "load_ai_index",
    "select_ai_skill",
    "validate_exported_openclaw_dir",
    "resolve_ai_release",
    "export_release_to_directory",
]
