from __future__ import annotations

from types import SimpleNamespace

from fastapi import Request

from server.ui.console import build_console_context, build_console_forbidden_context


def _make_request(path: str = "/", query_string: bytes = b"") -> Request:
    return Request(
        {
            "type": "http",
            "path": path,
            "query_string": query_string,
            "headers": [],
        }
    )


class TestBuildConsoleContext:
    def test_basic_structure(self):
        request = _make_request()
        ctx = build_console_context(
            request=request,
            title="Test",
            content="Hello",
            limit=10,
            items=[{"id": "1"}],
            cli_command="echo hi",
            stats=[{"label": "A", "value": "1"}],
        )
        assert ctx["title"] == "Test"
        assert ctx["content"] == "Hello"
        assert ctx["limit"] == 10
        assert ctx["items"] == [{"id": "1"}]
        assert ctx["cli_command"] == "echo hi"
        assert ctx["page_stats"] == [{"label": "A", "value": "1"}]
        assert ctx["page_mode"] == "console"
        assert "ui" in ctx

    def test_default_nav_links(self):
        request = _make_request()
        ctx = build_console_context(
            request=request,
            title="T",
            content="C",
            limit=0,
            items=[],
            cli_command="",
            stats=[],
        )
        assert len(ctx["nav_links"]) == 3

    def test_custom_nav_links(self):
        request = _make_request()
        custom_nav = [{"href": "/x", "label": "X"}]
        ctx = build_console_context(
            request=request,
            title="T",
            content="C",
            limit=0,
            items=[],
            cli_command="",
            stats=[],
            nav_links=custom_nav,
        )
        assert ctx["nav_links"] == custom_nav

    def test_lang_zh(self):
        request = _make_request(query_string=b"lang=zh")
        ctx = build_console_context(
            request=request,
            title="T",
            content="C",
            limit=0,
            items=[],
            cli_command="",
            stats=[],
        )
        assert ctx["page_eyebrow"] == "作者控制台"
        assert ctx["page_kicker"] == "兼容模式"


class TestBuildConsoleForbiddenContext:
    def test_structure(self):
        request = _make_request(query_string=b"lang=en")
        user = SimpleNamespace(role="contributor")
        ctx = build_console_forbidden_context(
            request=request,
            user=user,
            allowed_roles=("maintainer",),
        )
        assert "denied_title" in ctx
        assert "denied_body" in ctx
        assert ctx["denied_home_href"] == "/?lang=en"
        assert "ui" in ctx
        assert ctx["ui"]["page_kicker"] == "Access limited"

    def test_zh_lang(self):
        request = _make_request(query_string=b"lang=zh")
        user = SimpleNamespace(role="contributor")
        ctx = build_console_forbidden_context(
            request=request,
            user=user,
            allowed_roles=("maintainer",),
        )
        assert "作者台访问受限" in ctx["denied_title"]
