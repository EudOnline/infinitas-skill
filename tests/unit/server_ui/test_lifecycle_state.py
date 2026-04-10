from __future__ import annotations

from types import SimpleNamespace

from server.ui.lifecycle_actions import build_skills_overview_actions
from server.ui.lifecycle_state import (
    build_access_tokens_state,
    build_release_share_state,
)
from server.ui.navigation import build_share_rows


def test_build_skills_overview_actions_bundles_items_and_lang_aware_links(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.ui.lifecycle_actions.build_skill_items",
        lambda **kwargs: [{"id": "skill"}],
    )
    monkeypatch.setattr(
        "server.ui.lifecycle_actions.build_draft_items",
        lambda **kwargs: [{"id": "draft"}],
    )
    monkeypatch.setattr(
        "server.ui.lifecycle_actions.build_release_items",
        lambda **kwargs: [{"id": "release"}],
    )
    monkeypatch.setattr(
        "server.ui.lifecycle_actions.build_share_items",
        lambda **kwargs: [{"id": "share"}],
    )
    monkeypatch.setattr(
        "server.ui.lifecycle_actions.build_review_items",
        lambda **kwargs: [{"id": "review"}],
    )
    monkeypatch.setattr(
        "server.ui.lifecycle_actions.with_lang",
        lambda path, lang: f"{path}?lang={lang}",
    )

    payload = build_skills_overview_actions(
        skills=[],
        drafts=[],
        versions=[],
        releases=[],
        exposures=[],
        review_cases=[],
        principals_by_id={},
        drafts_by_skill={},
        versions_by_skill={},
        releases_by_id={},
        releases_by_version={},
        exposures_by_id={},
        exposures_by_release={},
        review_cases_by_exposure={},
        versions_by_id={},
        skills_by_id={},
        lang="en",
        limit=12,
    )

    assert payload == {
        "skill_items": [{"id": "skill"}],
        "draft_items": [{"id": "draft"}],
        "release_items": [{"id": "release"}],
        "share_items": [{"id": "share"}],
        "review_items": [{"id": "review"}],
        "access_href": "/access/tokens?lang=en",
        "review_cases_href": "/review-cases?lang=en",
    }


def test_build_access_tokens_state_preserves_credential_and_grant_rows() -> None:
    payload = build_access_tokens_state(
        credential_rows=[{"id": 1, "type": "token"}],
        grant_rows=[{"id": 2, "grant_type": "share"}],
    )

    assert payload == {
        "credential_rows": [{"id": 1, "type": "token"}],
        "grant_rows": [{"id": 2, "grant_type": "share"}],
    }


def test_build_share_rows_marks_blocking_review_exposure_as_not_activatable() -> None:
    exposure = SimpleNamespace(
        id=11,
        audience_type="public",
        listing_mode="listed",
        install_mode="enabled",
        review_requirement="blocking",
        state="review_open",
    )
    review_case = SimpleNamespace(state="open")

    rows = build_share_rows(
        exposures=[exposure],
        review_cases_by_exposure={11: [review_case]},
        grants_by_exposure={},
        lang="en",
    )

    assert rows == [
        {
            "id": 11,
            "audience": "Public",
            "audience_raw": "public",
            "listing_mode": "Listed",
            "listing_mode_raw": "listed",
            "install_mode": "Install enabled",
            "install_mode_raw": "enabled",
            "review_requirement": "Blocking review",
            "review_requirement_raw": "blocking",
            "review_case_state": "Open",
            "review_case_state_raw": "open",
            "requested_review_mode_raw": "none",
            "grant_count": 0,
            "state": "Review open",
            "state_raw": "review_open",
            "can_activate": False,
            "can_revoke": True,
            "can_patch": True,
            "activation_block_reason": "blocking_review_open",
        }
    ]


def test_build_share_rows_marks_private_pending_exposure_as_activatable() -> None:
    exposure = SimpleNamespace(
        id=12,
        audience_type="private",
        listing_mode="direct_only",
        install_mode="disabled",
        review_requirement="none",
        state="pending_policy",
        policy_snapshot_json='{"requested_review_mode":"advisory"}',
    )

    rows = build_share_rows(
        exposures=[exposure],
        review_cases_by_exposure={},
        grants_by_exposure={12: [object(), object()]},
        lang="en",
    )

    assert rows[0]["can_activate"] is True
    assert rows[0]["activation_block_reason"] == ""
    assert rows[0]["can_revoke"] is True
    assert rows[0]["can_patch"] is True
    assert rows[0]["review_case_state_raw"] == "none"
    assert rows[0]["requested_review_mode_raw"] == "advisory"


def test_build_share_rows_does_not_emit_block_reason_for_active_exposure() -> None:
    exposure = SimpleNamespace(
        id=13,
        audience_type="grant",
        listing_mode="listed",
        install_mode="enabled",
        review_requirement="advisory",
        state="active",
        policy_snapshot_json='{"requested_review_mode":"advisory"}',
    )

    rows = build_share_rows(
        exposures=[exposure],
        review_cases_by_exposure={},
        grants_by_exposure={},
        lang="en",
    )

    assert rows[0]["can_activate"] is False
    assert rows[0]["can_revoke"] is True
    assert rows[0]["can_patch"] is True
    assert rows[0]["activation_block_reason"] == ""


def test_build_release_share_state_exposes_canonical_exposure_policy() -> None:
    release = SimpleNamespace(
        id=21,
        platform_compatibility_json="{}",
    )
    version = SimpleNamespace(version="1.2.3")
    skill = SimpleNamespace(display_name="Skill")

    payload = build_release_share_state(
        release=release,
        version=version,
        skill=skill,
        share_rows=[],
        lang="en",
    )

    assert payload["release"]["exposure_policy"] == {
        "private": {
            "allowed_requested_review_modes": ["none"],
            "effective_requested_review_mode": "none",
            "effective_review_requirement": "none",
        },
        "authenticated": {
            "allowed_requested_review_modes": ["none"],
            "effective_requested_review_mode": "none",
            "effective_review_requirement": "none",
        },
        "grant": {
            "allowed_requested_review_modes": ["none", "advisory", "blocking"],
            "effective_requested_review_mode": None,
            "effective_review_requirement": None,
        },
        "public": {
            "allowed_requested_review_modes": ["blocking"],
            "effective_requested_review_mode": "blocking",
            "effective_review_requirement": "blocking",
        },
    }
