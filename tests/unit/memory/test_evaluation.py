from __future__ import annotations

from infinitas_skill.memory.evaluation import (
    build_recommendation_usefulness_outcome,
    summarize_memory_usefulness,
)


def test_build_recommendation_usefulness_outcome_tracks_correct_restraint() -> None:
    case = {
        "name": "negative_memory_should_not_take_over",
        "memory_context_enabled": True,
        "expected_winner": "team/alpha-safe",
        "expected_memory_used": False,
    }
    payload = {
        "results": [{"qualified_name": "team/alpha-safe"}],
        "explanation": {
            "memory_summary": {
                "used": False,
                "curation_summary": {"kept_count": 1},
            }
        },
    }

    outcome = build_recommendation_usefulness_outcome(case, payload)

    assert outcome["winner_match"] is True
    assert outcome["beneficial_use"] is False
    assert outcome["correct_restraint"] is True
    assert outcome["quality_success"] is True


def test_summarize_memory_usefulness_reports_counts_and_rates() -> None:
    recommendation_outcomes = [
        {
            "quality_success": True,
            "beneficial_use": True,
            "correct_restraint": False,
            "memory_enabled": True,
            "curation_kept": True,
        },
        {
            "quality_success": True,
            "beneficial_use": False,
            "correct_restraint": True,
            "memory_enabled": True,
            "curation_kept": False,
        },
    ]
    inspect_outcomes = [
        {
            "quality_success": True,
            "beneficial_use": True,
            "correct_restraint": False,
            "memory_enabled": True,
            "curation_kept": True,
        }
    ]

    summary = summarize_memory_usefulness(
        recommendation_outcomes=recommendation_outcomes,
        inspect_outcomes=inspect_outcomes,
    )

    assert summary["overall"]["cases"] == 3
    assert summary["overall"]["beneficial_use_cases"] == 2
    assert summary["overall"]["correct_restraint_cases"] == 1
    assert summary["overall"]["quality_success_rate"] == 1.0
    assert summary["recommendation"]["curation_keep_rate"] == 0.5
