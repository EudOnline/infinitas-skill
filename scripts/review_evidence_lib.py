#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

REVIEW_EVIDENCE_FILENAME = 'review-evidence.json'
ALLOWED_DECISIONS = {'approved', 'rejected'}


class ReviewEvidenceError(Exception):
    pass


def review_evidence_path(skill_dir: Path) -> Path:
    return Path(skill_dir).resolve() / REVIEW_EVIDENCE_FILENAME


def _parse_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_review_evidence(skill_dir: Path):
    path = review_evidence_path(skill_dir)
    if not path.exists():
        return {
            'version': 1,
            'entries': [],
            'path': str(path),
        }

    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise ReviewEvidenceError(f'review evidence file is not valid JSON: {path} ({exc})') from exc

    if not isinstance(payload, dict):
        raise ReviewEvidenceError(f'review evidence must be a JSON object: {path}')

    version = payload.get('version', 1)
    if not isinstance(version, int) or version < 1:
        raise ReviewEvidenceError(f'review evidence version must be a positive integer: {path}')

    entries = payload.get('entries', [])
    if not isinstance(entries, list):
        raise ReviewEvidenceError(f'review evidence entries must be an array: {path}')

    normalized = []
    seen_reviewers = set()
    for index, raw_entry in enumerate(entries):
        entry_path = f'{path} entry {index + 1}'
        if not isinstance(raw_entry, dict):
            raise ReviewEvidenceError(f'review evidence entry must be an object: {entry_path}')

        unknown = sorted(set(raw_entry) - {'source', 'source_kind', 'source_ref', 'reviewer', 'decision', 'at', 'url', 'note'})
        if unknown:
            raise ReviewEvidenceError(f'review evidence entry has unsupported keys: {entry_path}: {", ".join(unknown)}')

        normalized_entry = {}
        for key in ['source', 'source_kind', 'source_ref', 'reviewer', 'decision', 'at']:
            value = raw_entry.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ReviewEvidenceError(f'review evidence entry is missing required field {key!r}: {entry_path}')
            normalized_entry[key] = value.strip()

        if normalized_entry['decision'] not in ALLOWED_DECISIONS:
            raise ReviewEvidenceError(f"review evidence entry has invalid decision {normalized_entry['decision']!r}: {entry_path}")
        if _parse_timestamp(normalized_entry['at']) is None:
            raise ReviewEvidenceError(f"review evidence entry has invalid timestamp {normalized_entry['at']!r}: {entry_path}")

        reviewer = normalized_entry['reviewer']
        if reviewer in seen_reviewers:
            raise ReviewEvidenceError(f"review evidence has duplicate reviewer identity collision for {reviewer!r}: {path}")
        seen_reviewers.add(reviewer)

        for key in ['url', 'note']:
            value = raw_entry.get(key)
            if value is None:
                normalized_entry[key] = None
                continue
            if not isinstance(value, str) or not value.strip():
                raise ReviewEvidenceError(f'review evidence entry field {key!r} must be a non-empty string when present: {entry_path}')
            normalized_entry[key] = value.strip()

        normalized.append(normalized_entry)

    return {
        'version': version,
        'entries': normalized,
        'path': str(path),
    }
