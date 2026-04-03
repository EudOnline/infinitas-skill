from __future__ import annotations

from infinitas_skill.discovery.recommendation_explanation import (
    build_recommendation_explanation,
)


def test_build_recommendation_explanation_includes_memory_summary_and_winner_confidence():
    scored = [
        (
            1650,
            -100,
            "team/beta-preferred",
            {
                "qualified_name": "team/beta-preferred",
                "recommendation_reason": "private registry match; target-agent compatible",
                "ranking_factors": {
                    "compatibility": True,
                    "match_strength": 2,
                    "trust": {"state": "verified", "score": 3},
                    "quality": 82,
                    "verification_freshness_score": 20260403,
                },
                "comparative_signals": {
                    "rank": 1,
                    "score_gap_from_top": 0,
                    "quality_gap_from_runner_up": 12,
                    "verification_freshness_gap_from_runner_up": 5,
                    "compatibility_gap_from_runner_up": "same",
                },
                "confidence": {"level": "high", "reasons": ["target-agent compatible"]},
            },
        ),
        (
            1600,
            -100,
            "team/alpha-safe",
            {
                "qualified_name": "team/alpha-safe",
                "ranking_factors": {
                    "compatibility": True,
                    "match_strength": 2,
                    "trust": {"state": "verified", "score": 3},
                    "quality": 70,
                    "verification_freshness_score": 20260398,
                },
                "comparative_signals": {
                    "rank": 2,
                    "score_gap_from_top": 50,
                    "quality_gap_from_top": 12,
                    "verification_freshness_gap_from_top": 5,
                    "compatibility_gap_from_top": "same",
                },
            },
        ),
    ]

    explanation = build_recommendation_explanation(
        scored=scored,
        visible=[scored[0][3], scored[1][3]],
        memory_context={
            "backend": "fake",
            "status": "matched",
            "error": None,
        },
        memory_records_count=2,
        memory_context_enabled=True,
    )

    assert explanation["memory_summary"] == {
        "used": False,
        "backend": "fake",
        "matched_count": 2,
        "advisory_only": True,
        "status": "matched",
    }
    assert explanation["winner"] == "team/beta-preferred"
    assert explanation["runner_up"] == "team/alpha-safe"
    assert explanation["winner_confidence"]["level"] == "high"
    assert "comparison_summary" in explanation
