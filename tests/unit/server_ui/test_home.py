from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from server.ui.home import (
    _calculate_skill_rating,
    _get_skill_icon,
    _read_json,
)


class TestReadJson:
    def test_reads_valid_json(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            path.write_text('{"a": 1}', encoding="utf-8")
            assert _read_json(path) == {"a": 1}

    def test_missing_file(self):
        assert _read_json(Path("/nonexistent/path.json")) == {}

    def test_invalid_json(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text("not json", encoding="utf-8")
            assert _read_json(path) == {}


class TestGetSkillIcon:
    def test_discovery_tag(self):
        assert _get_skill_icon({"name": "x", "tags": ["discovery"]}) == "🔍"

    def test_search_tag(self):
        assert _get_skill_icon({"name": "x", "tags": ["search"]}) == "🔍"

    def test_install_tag(self):
        assert _get_skill_icon({"name": "x", "tags": ["install"]}) == "📦"

    def test_release_tag(self):
        assert _get_skill_icon({"name": "x", "tags": ["release"]}) == "🚀"

    def test_operate_tag(self):
        assert _get_skill_icon({"name": "x", "tags": ["operate"]}) == "🔧"

    def test_security_tag(self):
        assert _get_skill_icon({"name": "x", "tags": ["security"]}) == "🔒"

    def test_consume_in_name(self):
        assert _get_skill_icon({"name": "consume-tool", "tags": []}) == "🎯"

    def test_federation_in_name(self):
        assert _get_skill_icon({"name": "federation-hub", "tags": []}) == "🌐"

    def test_default_icon(self):
        assert _get_skill_icon({"name": "other", "tags": []}) == "🎯"

    def test_no_name_no_tags(self):
        assert _get_skill_icon({}) == "🎯"


class TestCalculateSkillRating:
    def test_approved_with_multiple_approvals(self):
        assert _calculate_skill_rating({"review_state": "approved", "approval_count": 2}) == 4.8

    def test_approved_with_one_approval(self):
        assert _calculate_skill_rating({"review_state": "approved", "approval_count": 1}) == 4.5

    def test_not_approved(self):
        assert _calculate_skill_rating({"review_state": "open", "approval_count": 5}) is None

    def test_no_review_state(self):
        assert _calculate_skill_rating({"approval_count": 5}) is None

    def test_zero_approvals(self):
        assert _calculate_skill_rating({"review_state": "approved", "approval_count": 0}) is None
