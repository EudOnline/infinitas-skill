from __future__ import annotations

from server.modules.access.authz import require_any_scope


class MockContext:
    def __init__(self, scopes=None):
        self.scopes = set(scopes or [])


class TestRequireAnyScope:
    def test_matching_scope(self):
        ctx = MockContext(["api:user", "artifact:download"])
        assert require_any_scope(ctx, {"api:user"}) is True

    def test_no_matching_scope(self):
        ctx = MockContext(["artifact:download"])
        assert require_any_scope(ctx, {"api:user"}) is False

    def test_multiple_allowed_one_matches(self):
        ctx = MockContext(["api:user"])
        assert require_any_scope(ctx, {"api:user", "admin:write"}) is True

    def test_empty_scopes(self):
        ctx = MockContext([])
        assert require_any_scope(ctx, {"api:user"}) is False

    def test_empty_allowed(self):
        ctx = MockContext(["api:user"])
        assert require_any_scope(ctx, set()) is False
