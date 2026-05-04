from __future__ import annotations

from src.infinitas_skill.server.health import emit_healthcheck_summary, normalize_health_url


class TestNormalizeHealthUrl:
    def test_adds_healthz(self):
        assert normalize_health_url("http://localhost:8000") == "http://localhost:8000/healthz"

    def test_already_has_healthz(self):
        assert (
            normalize_health_url("http://localhost:8000/healthz") == "http://localhost:8000/healthz"
        )

    def test_trailing_slash(self):
        assert normalize_health_url("http://localhost:8000/") == "http://localhost:8000/healthz"


class TestEmitHealthcheckSummary:
    def test_json_output(self, capsys):
        summary = {
            "api": {"url": "http://localhost/healthz"},
            "repo": {"path": "/repo", "clean": True},
            "artifacts": {"path": "/artifacts"},
            "database": {"path": "/db"},
        }
        emit_healthcheck_summary(summary, as_json=True)
        captured = capsys.readouterr()
        assert "http://localhost/healthz" in captured.out

    def test_text_output(self, capsys):
        summary = {
            "api": {"url": "http://localhost/healthz"},
            "repo": {"path": "/repo", "clean": True},
            "artifacts": {"path": "/artifacts"},
            "database": {"path": "/db"},
        }
        emit_healthcheck_summary(summary, as_json=False)
        captured = capsys.readouterr()
        assert "OK: api" in captured.out
        assert "OK: repo" in captured.out
