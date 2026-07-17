from __future__ import annotations

from src.infinitas_skill.skills.schema_version import validate_schema_version


class TestValidateSchemaVersion:
    def test_valid_version(self):
        version, errors = validate_schema_version({"schema_version": 1})
        assert version == 1
        assert errors == []

    def test_missing_field_is_rejected(self):
        version, errors = validate_schema_version({})
        assert version is None
        assert errors == ["missing required schema_version"]

    def test_non_dict_payload(self):
        version, errors = validate_schema_version("not a dict")
        assert version is None
        assert len(errors) == 1
        assert "requires an object payload" in errors[0]

    def test_non_integer_version(self):
        version, errors = validate_schema_version({"schema_version": "1"})
        assert version is None
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
