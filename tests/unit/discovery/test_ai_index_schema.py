from __future__ import annotations

import json
from pathlib import Path


def test_ai_index_schema_is_valid_json_and_models_verified_support() -> None:
    root = Path(__file__).resolve().parents[3]
    schema = json.loads((root / "schemas" / "ai-index.schema.json").read_text(encoding="utf-8"))

    skill_properties = schema["properties"]["skills"]["items"]["properties"]
    assert skill_properties["verified_support"]["type"] == "object"
    assert skill_properties["quality_score"]["type"] == ["number", "null"]
