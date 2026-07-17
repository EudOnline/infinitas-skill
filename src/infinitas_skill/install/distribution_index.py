"""Distribution index loading for install resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinitas_skill.hashing import sha256_file


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_distribution_index(root: str | Path) -> list[dict[str, Any]]:
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
        actual = sha256_file(index_path)
        if expected != actual:
            raise ValueError(f"distribution index integrity check failed: {index_path}")
    return skills
