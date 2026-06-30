from __future__ import annotations

from server.modules.shared.json import dumps_json, loads_json
from server.modules.shared.metadata import NAMING_CONVENTION, SHARED_METADATA


class TestDumpsJson:
    def test_compact_output(self):
        result = dumps_json({"a": 1, "b": 2})
        assert result == '{"a":1,"b":2}'

    def test_non_ascii(self):
        result = dumps_json({"name": "中文"})
        assert "中文" in result


class TestLoadsJson:
    def test_valid_json(self):
        assert loads_json('{"a": 1}', default={}) == {"a": 1}

    def test_invalid_returns_default(self):
        assert loads_json("not json", default={}) == {}

    def test_none_returns_default(self):
        assert loads_json(None, default=[]) == []


class TestMetadata:
    def test_naming_convention(self):
        assert "ix_" in NAMING_CONVENTION["ix"]
        assert "uq_" in NAMING_CONVENTION["uq"]
        assert "pk_" in NAMING_CONVENTION["pk"]

    def test_shared_metadata(self):
        assert isinstance(SHARED_METADATA.naming_convention, dict)
