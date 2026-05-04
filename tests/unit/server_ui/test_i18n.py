from __future__ import annotations

from fastapi import Request

from server.ui.i18n import (
    load_locale,
    pick_lang,
    request_path_with_query,
    resolve_language,
    t,
    with_lang,
)


def _make_request(path: str, query_string: bytes = b"") -> Request:
    return Request(
        {
            "type": "http",
            "path": path,
            "query_string": query_string,
            "headers": [],
        }
    )


class TestPickLang:
    def test_zh_returns_first(self):
        assert pick_lang("zh", "中文", "English") == "中文"

    def test_en_returns_second(self):
        assert pick_lang("en", "中文", "English") == "English"

    def test_other_defaults_to_en(self):
        # Non-zh falls through to en
        assert pick_lang("ja", "中文", "English") == "English"


class TestLoadLocale:
    def test_existing_locale(self):
        locale = load_locale("zh")
        assert isinstance(locale, dict)
        assert len(locale) > 0

    def test_nonexistent_locale(self):
        locale = load_locale("xx")
        assert locale == {}


class TestT:
    def test_existing_key(self):
        assert t("zh", "brand_subtitle") != "brand_subtitle"

    def test_missing_key(self):
        assert t("zh", "nonexistent_key_xyz") == "nonexistent_key_xyz"

    def test_en_locale(self):
        assert t("en", "brand_subtitle") != "brand_subtitle"


class TestWithLang:
    def test_adds_lang_query(self):
        assert with_lang("/path", "en") == "/path?lang=en"

    def test_preserves_existing_query(self):
        assert with_lang("/path?a=1", "zh") == "/path?a=1&lang=zh"

    def test_empty_href(self):
        assert with_lang("", "en") == ""


class TestResolveLanguage:
    def test_query_param_lang(self):
        request = Request({"type": "http", "query_string": b"lang=en", "headers": []})
        assert resolve_language(request) == "en"

    def test_defaults_to_zh(self):
        request = Request({"type": "http", "query_string": b"", "headers": []})
        assert resolve_language(request) == "zh"

    def test_query_param_zh(self):
        request = Request({"type": "http", "query_string": b"lang=zh", "headers": []})
        assert resolve_language(request) == "zh"


class TestRequestPathWithQuery:
    def test_returns_path(self):
        request = _make_request("/test")
        assert request_path_with_query(request) == "/test"

    def test_includes_query(self):
        request = _make_request("/test", b"a=1")
        assert request_path_with_query(request) == "/test?a=1"
