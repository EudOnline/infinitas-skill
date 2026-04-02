"""Distribution index loading for install resolution."""

from __future__ import annotations

import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_distribution_index(root):
    root = Path(root).resolve()
    index_path = root / "catalog" / "distributions.json"
    if not index_path.exists():
        return []
    payload = load_json(index_path)
    skills = payload.get("skills")
    return skills if isinstance(skills, list) else []
