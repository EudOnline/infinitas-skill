from __future__ import annotations

from server.ui.lifecycle_actions import build_skills_overview_actions
from server.ui.lifecycle_state import build_access_tokens_state


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
