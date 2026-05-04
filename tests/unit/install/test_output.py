from __future__ import annotations

from src.infinitas_skill.install.output import error_to_payload, plan_to_text


class TestErrorToPayload:
    def test_basic(self):
        class FakeError:
            message = "something failed"
            details = {"code": 500}

        result = error_to_payload(FakeError())
        assert result["error"] == "something failed"
        assert result["code"] == 500

    def test_no_details(self):
        class FakeError:
            message = "simple error"
            details = None

        result = error_to_payload(FakeError())
        assert result["error"] == "simple error"


class TestPlanToText:
    def test_basic(self):
        plan = {
            "root": {"qualified_name": "acme/skill", "version": "1.0.0", "registry": "local"},
            "steps": [
                {
                    "action": "install",
                    "stage": "active",
                    "registry": "local",
                    "qualified_name": "acme/skill",
                    "version": "1.0.0",
                    "source_commit": "abc123def456",
                }
            ],
        }
        result = plan_to_text(plan)
        assert "resolution plan:" in result
        assert "acme/skill@1.0.0" in result
        assert "[install]" in result
        assert "abc123def456"[:12] in result

    def test_with_tag(self):
        plan = {
            "root": {"name": "skill", "version": "1.0.0", "registry": "local"},
            "steps": [
                {
                    "action": "install",
                    "stage": "active",
                    "registry": "local",
                    "name": "skill",
                    "version": "1.0.0",
                    "source_tag": "v1.0.0",
                }
            ],
        }
        result = plan_to_text(plan)
        assert "tag=v1.0.0" in result

    def test_with_requester(self):
        plan = {
            "root": {"name": "skill", "version": "1.0.0", "registry": "local"},
            "steps": [
                {
                    "action": "install",
                    "stage": "active",
                    "registry": "local",
                    "name": "skill",
                    "version": "1.0.0",
                    "requested_by": [{"by": "other", "version": "2.0.0", "constraint": ">=1.0.0"}],
                }
            ],
        }
        result = plan_to_text(plan)
        assert "requested by" in result
