from __future__ import annotations

from src.infinitas_skill.memory.scopes import dedupe_scope_refs, scope_ref, task_scope_ref


class TestScopeRef:
    def test_basic(self):
        assert scope_ref("task", "hello") == "task:hello"

    def test_whitespace_trimmed(self):
        assert scope_ref("  task  ", "  hello  ") == "task:hello"

    def test_none_value(self):
        assert scope_ref("task", None) is None

    def test_empty_prefix(self):
        assert scope_ref("", "hello") is None


class TestTaskScopeRef:
    def test_basic(self):
        assert task_scope_ref("find skill") == "task:find"

    def test_none(self):
        assert task_scope_ref(None) is None

    def test_whitespace(self):
        assert task_scope_ref("  deploy app  ") == "task:deploy"


class TestDedupeScopeRefs:
    def test_dedupes(self):
        assert dedupe_scope_refs(["a", "b", "a", "c"]) == ["a", "b", "c"]

    def test_skips_none(self):
        assert dedupe_scope_refs(["a", None, "b"]) == ["a", "b"]

    def test_empty(self):
        assert dedupe_scope_refs([]) == []
