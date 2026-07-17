from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.policy.review_evidence import import_review_evidence


def test_import_review_evidence_validates_before_replacing(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    input_path = tmp_path / "evidence.json"
    input_path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "source": "codex-review",
                        "source_kind": "platform",
                        "source_ref": "review-1",
                        "reviewer": "alice",
                        "decision": "approved",
                        "at": "2026-07-14T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = import_review_evidence(skill_dir, input_path)

    assert result["imported_count"] == 1
    assert result["reviewers"] == ["alice"]
    assert (skill_dir / "review-evidence.json").is_file()
