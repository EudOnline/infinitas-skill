from __future__ import annotations

from infinitas_skill.install.target_validation import selected_conflict_reason


def test_selected_conflict_reason_blocks_dependency_collision() -> None:
    existing = {
        "other/demo-skill": {
            "name": "demo-skill",
            "qualified_name": "other/demo-skill",
            "conflicts_with": [],
        }
    }
    candidate = {
        "name": "demo-skill",
        "qualified_name": "demo/demo-skill",
        "conflicts_with": [],
    }

    reason = selected_conflict_reason(candidate, existing)

    assert reason is not None
    assert "cannot select both" in reason
    assert "installed skill state is still keyed by bare skill name" in reason
