"""Validation for rendered skill directories consumed by the installer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from infinitas_skill.policy.skill_identity import (
    NamespacePolicyError,
    load_namespace_policy,
    namespace_policy_report,
    validate_identity_metadata,
)
from infinitas_skill.skills.schema_version import validate_schema_version

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?$")
_SECRET_RE = re.compile(
    rb"(?:gh[pousr]_|github_pat_|sk-[A-Za-z0-9_-]{10,}|"
    rb"AIza[0-9A-Za-z_-]{20,}|xox[baprs]-|"
    rb"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PGP|PRIVATE KEY)|"
    rb"Authorization:\s*Bearer\s+[A-Za-z0-9._-]+)"
)
_REQUIRED_META_FIELDS = {
    "schema_version",
    "name",
    "version",
    "status",
    "summary",
    "owner",
    "review_state",
    "risk_level",
    "distribution",
}
_STAGES = {"incubating", "active", "archived"}


class SkillValidationError(Exception):
    """Raised when a rendered skill directory is not installable."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _frontmatter_field(skill_md: Path, field: str) -> str | None:
    prefix = f"{field}: "
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            return value or None
    return None


def _secret_matches(skill_dir: Path) -> list[str]:
    matches: list[str] = []
    for path in sorted(candidate for candidate in skill_dir.rglob("*") if candidate.is_file()):
        try:
            content = path.read_bytes()
        except OSError:
            continue
        if _SECRET_RE.search(content):
            matches.append(str(path.relative_to(skill_dir)))
    return matches


def _validate_meta_shape(meta: dict[str, Any], *, basename: str, stage: str) -> list[str]:
    errors: list[str] = []
    _version, schema_errors = validate_schema_version(meta)
    errors.extend(schema_errors)
    for field in sorted(_REQUIRED_META_FIELDS - set(meta)):
        errors.append(f"_meta.json missing required field: {field}")

    name = meta.get("name")
    if isinstance(name, str) and name != basename and stage != "archived":
        errors.append(f"_meta.json name ({name}) does not match folder name ({basename})")
    version = meta.get("version")
    if not isinstance(version, str) or not _SEMVER_RE.match(version):
        errors.append(f"version is not semver-like: {version}")
    status = meta.get("status")
    if status not in _STAGES:
        errors.append(f"invalid status: {status}")
    if stage in _STAGES and status != stage:
        errors.append(f"_meta.json status ({status}) does not match parent dir ({stage})")
    if meta.get("review_state") not in {"draft", "under-review", "approved", "rejected"}:
        errors.append(f"invalid review_state: {meta.get('review_state')}")
    if meta.get("risk_level") not in {"low", "medium", "high"}:
        errors.append(f"invalid risk_level: {meta.get('risk_level')}")
    if not isinstance(meta.get("distribution"), dict):
        errors.append("distribution must be an object")

    _identity, identity_errors = validate_identity_metadata(meta)
    errors.extend(identity_errors)
    return errors


def _required_file_errors(path: Path) -> list[str]:
    errors: list[str] = []
    if not (path / "SKILL.md").is_file():
        errors.append(f"missing SKILL.md in {path}")
    if not (path / "_meta.json").is_file():
        errors.append(f"missing _meta.json in {path}")
    if path.parent.name != "templates" and not (path / "CHANGELOG.md").is_file():
        errors.append(f"missing CHANGELOG.md in {path}")
    return errors


def _content_errors(path: Path, meta: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    skill_md = path / "SKILL.md"
    skill_name = _frontmatter_field(skill_md, "name")
    description = _frontmatter_field(skill_md, "description")
    if not skill_name:
        errors.append("missing name field in SKILL.md")
    elif skill_name != meta.get("name"):
        errors.append(
            f"SKILL.md name ({skill_name}) does not match _meta.json name ({meta.get('name')})"
        )
    if not description:
        errors.append("missing description field in SKILL.md")

    tests = meta.get("tests")
    smoke = tests.get("smoke", "tests/smoke.md") if isinstance(tests, dict) else "tests/smoke.md"
    if not isinstance(smoke, str) or not (path / smoke).is_file():
        errors.append(f"missing smoke test file: {smoke}")
    return errors


def _namespace_errors(path: Path, root: Path) -> list[str]:
    try:
        path.relative_to(root / "skills")
    except ValueError:
        return []
    try:
        policy = load_namespace_policy(root)
        report = namespace_policy_report(path, root=root, policy=policy)
    except NamespacePolicyError as exc:
        return list(exc.errors)
    return [str(error) for error in report.get("errors", [])]


def validate_installable_skill_dir(skill_dir: str | Path, *, repo_root: str | Path) -> None:
    """Validate one rendered skill tree or raise ``SkillValidationError``."""

    root = Path(repo_root).resolve()
    path = Path(skill_dir).resolve()
    errors: list[str] = []
    if not path.is_dir():
        raise SkillValidationError([f"missing directory: {path}"])

    meta_path = path / "_meta.json"
    errors.extend(_required_file_errors(path))
    if errors:
        raise SkillValidationError(errors)

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillValidationError([f"invalid JSON in _meta.json: {exc}"]) from exc
    if not isinstance(meta, dict):
        raise SkillValidationError(["_meta.json must contain an object"])

    stage = path.parent.name
    errors.extend(_validate_meta_shape(meta, basename=path.name, stage=stage))
    errors.extend(_content_errors(path, meta))
    errors.extend(_namespace_errors(path, root))

    secret_files = _secret_matches(path)
    if secret_files:
        errors.append("possible secrets detected in: " + ", ".join(secret_files))
    if errors:
        raise SkillValidationError(errors)


__all__ = ["SkillValidationError", "validate_installable_skill_dir"]
