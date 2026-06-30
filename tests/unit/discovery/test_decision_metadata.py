from __future__ import annotations

from infinitas_skill.discovery.decision_metadata import canonical_decision_metadata


def test_normalizes_source_metadata() -> None:
    payload = canonical_decision_metadata(
        {
            "use_when": [" Need repo operations ", "", 42, "Need release guidance"],
            "avoid_when": ["   ", "Need public marketplace publishing"],
            "capabilities": [" repo-operations ", None, "release-guidance"],
            "runtime_assumptions": [
                " Git checkout available ",
                "",
                "Repository scripts executable",
            ],
            "maturity": " stable ",
            "quality_score": 90,
        }
    )
    assert payload == {
        "use_when": ["Need repo operations", "Need release guidance"],
        "avoid_when": ["Need public marketplace publishing"],
        "capabilities": ["repo-operations", "release-guidance"],
        "runtime_assumptions": ["Git checkout available", "Repository scripts executable"],
        "maturity": "stable",
        "quality_score": 90,
    }


def test_projects_generated_entry_fields() -> None:
    payload = canonical_decision_metadata(
        {
            "use_when": ["Need immutable install"],
            "avoid_when": ["Need mutable prototype copy"],
            "capabilities": ["immutable-install"],
            "runtime_assumptions": ["Release artifacts are available"],
            "maturity": "beta",
            "quality_score": "not-an-int",
        }
    )
    assert payload["quality_score"] == 0
    assert payload["maturity"] == "beta"


def test_applies_stable_defaults() -> None:
    assert canonical_decision_metadata({}) == {
        "use_when": [],
        "avoid_when": [],
        "capabilities": [],
        "runtime_assumptions": [],
        "maturity": "unknown",
        "quality_score": 0,
    }
