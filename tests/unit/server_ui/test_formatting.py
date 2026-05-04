from __future__ import annotations

from server.ui.formatting import (
    humanize_audience_type,
    humanize_identifier,
    humanize_install_mode,
    humanize_job_kind,
    humanize_listing_mode,
    humanize_object_kind,
    humanize_review_gate,
    humanize_role,
    humanize_status,
    humanize_timestamp,
    load_json_list,
    load_json_object,
    localized_stamp,
    short_stamp,
)


class TestLoadJsonObject:
    def test_valid_json(self):
        assert load_json_object('{"a": 1}') == {"a": 1}

    def test_none_returns_empty(self):
        assert load_json_object(None) == {}

    def test_invalid_json_returns_empty(self):
        assert load_json_object("not json") == {}


class TestLoadJsonList:
    def test_valid_json(self):
        assert load_json_list('["a", "b"]') == ["a", "b"]

    def test_none_returns_empty(self):
        assert load_json_list(None) == []

    def test_invalid_json_returns_empty(self):
        assert load_json_list("not json") == []


class TestShortStamp:
    def test_iso_timestamp(self):
        assert short_stamp("2026-04-01T12:34:56+00:00") == "2026-04-01"

    def test_none_returns_no_snapshot(self):
        assert short_stamp(None) == "No snapshot"

    def test_short_string_unchanged(self):
        assert short_stamp("2026-04-01") == "2026-04-01"


class TestLocalizedStamp:
    def test_zh_format(self):
        result = localized_stamp("2026-04-01T12:34:56+00:00", "zh")
        assert "2026" in result
        assert "4" in result

    def test_en_format(self):
        result = localized_stamp("2026-04-01T12:34:56+00:00", "en")
        assert "2026" in result

    def test_none_returns_fallback(self):
        assert localized_stamp(None, "zh") == "暂无快照"
        assert localized_stamp(None, "en") == "No snapshot"


class TestHumanizeIdentifier:
    def test_snake_case(self):
        assert humanize_identifier("hello_world") == "Hello World"

    def test_none_returns_dash(self):
        assert humanize_identifier(None) == "-"


class TestHumanizeStatus:
    def test_active_falls_back_to_identifier(self):
        # Mapping is empty
        assert humanize_status("active", "zh") == "Active"

    def test_en_falls_back(self):
        assert humanize_status("pending", "en") == "Pending"

    def test_none_returns_dash(self):
        assert humanize_status(None, "zh") == "-"


class TestHumanizeJobKind:
    def test_known_kind(self):
        assert humanize_job_kind("materialize_release", "zh") == "生成发布产物"
        assert humanize_job_kind("materialize_release", "en") == "Materialize release"

    def test_unknown_kind(self):
        assert humanize_job_kind("sync", "en") == "Sync"


class TestHumanizeRole:
    def test_maintainer(self):
        # Mapping is empty, falls back to humanize_identifier
        assert humanize_role("maintainer", "zh") == "Maintainer"

    def test_contributor(self):
        assert humanize_role("contributor", "en") == "Contributor"

    def test_unknown_role(self):
        assert humanize_role("guest", "en") == "Guest"


class TestHumanizeObjectKind:
    def test_skill(self):
        # Mapping is empty, falls back to humanize_identifier
        assert humanize_object_kind("skill", "zh") == "Skill"

    def test_agent_preset(self):
        assert humanize_object_kind("agent_preset", "en") == "Agent Preset"


class TestHumanizeAudienceType:
    def test_public(self):
        # Mapping is empty, falls back to humanize_identifier
        assert humanize_audience_type("public", "zh") == "Public"

    def test_private(self):
        assert humanize_audience_type("private", "en") == "Private"


class TestHumanizeListingMode:
    def test_listed(self):
        # Mapping is empty, falls back to humanize_identifier
        assert humanize_listing_mode("listed", "zh") == "Listed"

    def test_unlisted(self):
        assert humanize_listing_mode("unlisted", "en") == "Unlisted"


class TestHumanizeInstallMode:
    def test_enabled(self):
        # Mapping is empty, falls back to humanize_identifier
        assert humanize_install_mode("enabled", "zh") == "Enabled"

    def test_disabled(self):
        assert humanize_install_mode("disabled", "en") == "Disabled"


class TestHumanizeReviewGate:
    def test_passed(self):
        # Mapping is empty, falls back to humanize_identifier
        assert humanize_review_gate("passed", "zh") == "Passed"

    def test_failed(self):
        assert humanize_review_gate("failed", "en") == "Failed"


class TestHumanizeTimestamp:
    def test_valid_iso(self):
        result = humanize_timestamp("2026-04-01T12:34:56+00:00")
        assert "2026" in result
        assert "UTC" in result

    def test_none_returns_dash(self):
        assert humanize_timestamp(None) == "-"

    def test_invalid_returns_raw(self):
        assert humanize_timestamp("not-a-date") == "not-a-date"
