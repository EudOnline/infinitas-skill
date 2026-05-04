from __future__ import annotations

from server.ui.navigation import (
    _build_exposure_policy,
    _derive_exposure_action_state,
    build_site_nav,
    first_by_id,
    group_by,
)


class FakeItem:
    def __init__(self, id: int, group_id: int | None = None):
        self.id = id
        self.group_id = group_id


class TestGroupBy:
    def test_groups_items(self):
        items = [FakeItem(1, 1), FakeItem(2, 1), FakeItem(3, 2)]
        result = group_by(items, "group_id")
        assert result[1] == [items[0], items[1]]
        assert result[2] == [items[2]]

    def test_skips_none_key(self):
        items = [FakeItem(1, None), FakeItem(2, 1)]
        result = group_by(items, "group_id")
        assert len(result.get(1, [])) == 1
        assert items[0] not in result.get(1, [])

    def test_empty_list(self):
        assert group_by([], "group_id") == {}


class TestFirstById:
    def test_returns_last_per_id(self):
        # Dict comprehension keeps the last occurrence
        items = [FakeItem(1), FakeItem(2), FakeItem(1)]
        result = first_by_id(items)
        assert result[1] == items[2]
        assert result[2] == items[1]

    def test_empty_list(self):
        assert first_by_id([]) == {}


class TestBuildSiteNav:
    def test_home_variant(self):
        nav = build_site_nav(home=True, lang="zh")
        assert len(nav) == 3
        assert nav[0]["href"] == "#start"
        assert nav[0]["label"] == "开始"

    def test_home_variant_en(self):
        nav = build_site_nav(home=True, lang="en")
        assert nav[0]["label"] == "Home base"

    def test_default_variant(self):
        nav = build_site_nav(home=False, lang="zh")
        assert len(nav) == 6
        assert nav[0]["href"] == "/?lang=zh"
        assert nav[0]["label"] == "首页"

    def test_library_variant(self):
        nav = build_site_nav(home=False, lang="en", variant="library")
        assert len(nav) == 6
        assert nav[1]["href"] == "/library?lang=en"
        assert nav[1]["label"] == "Library"


class TestBuildExposurePolicy:
    def test_private_policy(self):
        policy = _build_exposure_policy()
        assert policy["private"]["effective_review_requirement"] == "none"

    def test_public_policy(self):
        policy = _build_exposure_policy()
        assert policy["public"]["effective_review_requirement"] == "blocking"


class TestDeriveExposureActionState:
    class FakeExposure:
        def __init__(self, state: str, review_requirement: str = ""):
            self.state = state
            self.review_requirement = review_requirement

    def test_active_state(self):
        exposure = self.FakeExposure("active")
        result = _derive_exposure_action_state(exposure=exposure, review_case_state="open")
        assert result["can_activate"] is False
        assert result["can_revoke"] is True

    def test_revoked_state(self):
        exposure = self.FakeExposure("revoked")
        result = _derive_exposure_action_state(exposure=exposure, review_case_state="open")
        assert result["can_activate"] is False
        assert result["can_revoke"] is False

    def test_pending_blocking_approved(self):
        exposure = self.FakeExposure("pending_policy", "blocking")
        result = _derive_exposure_action_state(exposure=exposure, review_case_state="approved")
        assert result["can_activate"] is True
        assert result["activation_block_reason"] == ""

    def test_pending_blocking_open(self):
        exposure = self.FakeExposure("pending_policy", "blocking")
        result = _derive_exposure_action_state(exposure=exposure, review_case_state="open")
        assert result["can_activate"] is False
        assert result["activation_block_reason"] == "blocking_review_open"

    def test_pending_no_blocking(self):
        exposure = self.FakeExposure("pending_policy", "none")
        result = _derive_exposure_action_state(exposure=exposure, review_case_state="open")
        assert result["can_activate"] is True
