from __future__ import annotations

from src.infinitas_skill.skills.schema_version import (
    SUPPORTED_SCHEMA_VERSION,
    validate_schema_version,
)


class TestValidateSchemaVersion:
    def test_valid_version(self):
        version, errors = validate_schema_version({"schema_version": 1})
        assert version == 1
        assert errors == []

    def test_missing_field_returns_default(self):
        version, errors = validate_schema_version({})
        assert version == SUPPORTED_SCHEMA_VERSION
        assert errors == []

    def test_non_dict_payload(self):
        version, errors = validate_schema_version("not a dict")
        assert version == SUPPORTED_SCHEMA_VERSION
        assert len(errors) == 1
        assert "requires an object payload" in errors[0]

    def test_non_integer_version(self):
        version, errors = validate_schema_version({"schema_version": "1"})
        assert version == SUPPORTED_SCHEMA_VERSION
        assert len(errors) == 1
        assert "must be an integer" in errors[0]

    def test_unsupported_version(self):
        version, errors = validate_schema_version({"schema_version": 99})
        assert version == 99
        assert len(errors) == 1
        assert "unsupported" in errors[0]

    def test_custom_field(self):
        version, errors = validate_schema_version({"ver": 1}, field="ver")
        assert version == 1
        assert errors == []

    def test_custom_default(self):
        version, errors = validate_schema_version({}, default_version=2)
        assert version == 2
        assert errors == []
