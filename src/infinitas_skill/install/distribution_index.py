"""Distribution index loading for install resolution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_distribution_index(root):
    root = Path(root).resolve()
    index_path = root / "catalog" / "distributions.json"
    if not index_path.exists():
        return []
    payload = load_json(index_path)
    skills = payload.get("skills")
    if not isinstance(skills, list):
        return []
    checksum_path = index_path.with_suffix(".json.sha256")
    if checksum_path.exists():
        expected = checksum_path.read_text(encoding="utf-8").strip().split()[0]
        actual = _sha256_file(index_path)
        if expected != actual:
            raise ValueError(
                f"distribution index integrity check failed: {index_path}"
            )
    return skills
