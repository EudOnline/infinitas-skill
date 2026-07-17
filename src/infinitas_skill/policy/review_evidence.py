"""Review evidence normalization shared by package-native policy code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinitas_skill.policy.primitives import parse_timestamp

REVIEW_EVIDENCE_FILENAME = "review-evidence.json"
ALLOWED_DECISIONS = {"approved", "rejected"}


class ReviewEvidenceError(Exception):
    pass


def review_evidence_path(skill_dir: Path) -> Path:
    return Path(skill_dir).resolve() / REVIEW_EVIDENCE_FILENAME


def _load_evidence_payload(path: Path) -> tuple[int, list[object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewEvidenceError(
            f"review evidence file is not valid JSON: {path} ({exc})"
        ) from exc
    if not isinstance(payload, dict):
        raise ReviewEvidenceError(f"review evidence must be a JSON object: {path}")
    version = payload.get("version", 1)
    if not isinstance(version, int) or version < 1:
        raise ReviewEvidenceError(f"review evidence version must be a positive integer: {path}")
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        raise ReviewEvidenceError(f"review evidence entries must be an array: {path}")
    return version, entries


def _required_evidence_fields(raw_entry: dict, entry_path: str) -> dict[str, str | None]:
    normalized: dict[str, str | None] = {}
    for key in ["source", "source_kind", "source_ref", "reviewer", "decision", "at"]:
        value = raw_entry.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ReviewEvidenceError(
                f"review evidence entry is missing required field {key!r}: {entry_path}"
            )
        normalized[key] = value.strip()
    return normalized


def _normalize_evidence_entry(raw_entry: object, entry_path: str) -> dict[str, str | None]:
    if not isinstance(raw_entry, dict):
        raise ReviewEvidenceError(f"review evidence entry must be an object: {entry_path}")
    allowed = {"source", "source_kind", "source_ref", "reviewer", "decision", "at", "url", "note"}
    unknown = sorted(set(raw_entry) - allowed)
    if unknown:
        raise ReviewEvidenceError(
            f"review evidence entry has unsupported keys: {entry_path}: {', '.join(unknown)}"
        )
    normalized = _required_evidence_fields(raw_entry, entry_path)
    if normalized["decision"] not in ALLOWED_DECISIONS:
        raise ReviewEvidenceError(
            f"review evidence entry has invalid decision {normalized['decision']!r}: {entry_path}"
        )
    if parse_timestamp(normalized["at"]) is None:
        raise ReviewEvidenceError(
            f"review evidence entry has invalid timestamp {normalized['at']!r}: {entry_path}"
        )
    for key in ["url", "note"]:
        value = raw_entry.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ReviewEvidenceError(
                f"review evidence entry field {key!r} must be a non-empty string when present: "
                f"{entry_path}"
            )
        normalized[key] = value.strip() if isinstance(value, str) else None
    return normalized


def load_review_evidence(skill_dir: Path) -> dict[str, Any]:
    path = review_evidence_path(skill_dir)
    if not path.exists():
        return {
            "version": 1,
            "entries": [],
            "path": str(path),
        }

    version, entries = _load_evidence_payload(path)
    normalized: list[dict[str, str | None]] = []
    seen_reviewers: set[str | None] = set()
    for index, raw_entry in enumerate(entries):
        entry_path = f"{path} entry {index + 1}"
        normalized_entry = _normalize_evidence_entry(raw_entry, entry_path)
        reviewer = normalized_entry["reviewer"]
        if reviewer in seen_reviewers:
            raise ReviewEvidenceError(
                "review evidence has duplicate reviewer identity collision for "
                f"{reviewer!r}: {path}"
            )
        seen_reviewers.add(reviewer)

        normalized.append(normalized_entry)

    return {
        "version": version,
        "entries": normalized,
        "path": str(path),
    }


def import_review_evidence(skill_dir: Path, input_path: Path) -> dict[str, Any]:
    """Validate and replace one skill's normalized review evidence."""

    source = Path(input_path).resolve()
    if not source.is_file():
        raise ReviewEvidenceError(f"missing input file: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewEvidenceError(f"invalid JSON in input file {source}: {exc}") from exc

    target = review_evidence_path(skill_dir)
    previous = target.read_text(encoding="utf-8") if target.exists() else None
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        evidence = load_review_evidence(skill_dir)
    except ReviewEvidenceError:
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(previous, encoding="utf-8")
        raise
    entries = evidence.get("entries") or []
    return {
        "review_evidence_path": str(target),
        "imported_count": len(entries),
        "reviewers": [item.get("reviewer") for item in entries],
        "sources": sorted(
            {
                item.get("source_kind")
                for item in entries
                if isinstance(item, dict) and item.get("source_kind")
            }
        ),
    }


__all__ = [
    "REVIEW_EVIDENCE_FILENAME",
    "ReviewEvidenceError",
    "import_review_evidence",
    "load_review_evidence",
    "review_evidence_path",
]
