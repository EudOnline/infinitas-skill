from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from infinitas_skill.server.inspection_summary import (
    build_jobs_inspection_summary,
    build_release_inspection_summary,
    maybe_add_alert,
)


class _FakeResult:
    def __init__(self, *, all_values=None, scalar_values=None, scalar_one_value=None):
        self._all_values = all_values if all_values is not None else []
        self._scalar_values = scalar_values if scalar_values is not None else []
        self._scalar_one_value = scalar_one_value

    def all(self):
        return self._all_values

    def scalars(self):
        return self._scalar_values

    def scalar_one(self):
        return self._scalar_one_value


class _FakeSession:
    def __init__(self, results: list[_FakeResult]):
        self._results = list(results)

    def execute(self, _query):
        assert self._results, "unexpected query call with no queued fake result"
        return self._results.pop(0)


def test_maybe_add_alert_adds_entry_only_when_threshold_exceeded() -> None:
    alerts: list[dict] = []

    maybe_add_alert(alerts, kind="queued_jobs", label="queued jobs", actual=2, maximum=3)
    maybe_add_alert(alerts, kind="queued_jobs", label="queued jobs", actual=2, maximum=None)
    maybe_add_alert(alerts, kind="queued_jobs", label="queued jobs", actual=4, maximum=3)

    assert len(alerts) == 1
    assert alerts[0]["kind"] == "queued_jobs"
    assert alerts[0]["message"] == "queued jobs exceeded threshold: 4 > 3"


def test_build_release_inspection_summary_aggregates_audience_and_review_state() -> None:
    review_cases = [
        SimpleNamespace(exposure_id=1, state="approved"),
        SimpleNamespace(exposure_id=2, state=None),
    ]
    exposures = [
        SimpleNamespace(id=1, audience_type="public"),
        SimpleNamespace(id=2, audience_type="private"),
        SimpleNamespace(id=3, audience_type=None),
    ]
    session = _FakeSession(
        [
            _FakeResult(scalar_values=review_cases),
            _FakeResult(scalar_values=exposures),
        ]
    )

    summary = build_release_inspection_summary(session)

    assert summary["by_audience"] == {"private": 1, "public": 1, "unknown": 1}
    assert summary["by_audience_review_state"]["public"]["approved"] == 1
    assert summary["by_audience_review_state"]["private"]["none"] == 1
    assert summary["by_audience_review_state"]["unknown"]["none"] == 1


def test_build_jobs_inspection_summary_reports_counts_and_recent_lists(monkeypatch) -> None:
    monkeypatch.setattr(
        "infinitas_skill.server.inspection_summary.serialize_job",
        lambda job: {"id": job.id, "status": job.status},
    )

    now = datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc)
    queued = SimpleNamespace(
        id=10,
        status="queued",
        created_at=now - timedelta(minutes=45),
    )
    running = SimpleNamespace(
        id=11,
        status="running",
        created_at=now - timedelta(minutes=35),
        started_at=now - timedelta(minutes=30),
        lease_expires_at=now + timedelta(minutes=5),
    )
    stale_running = SimpleNamespace(
        id=14,
        status="running",
        created_at=now - timedelta(hours=2, minutes=5),
        started_at=now - timedelta(hours=2),
        lease_expires_at=now - timedelta(minutes=10),
    )
    failed = SimpleNamespace(id=12, status="failed")
    warning = SimpleNamespace(id=13, status="completed")
    reclaimed = SimpleNamespace(id=15, status="completed")

    session = _FakeSession(
        [
            _FakeResult(
                all_values=[("queued", 1), ("running", 2), ("failed", 3), ("completed", 4)]
            ),
            _FakeResult(scalar_one_value=5),
            _FakeResult(scalar_values=[failed]),
            _FakeResult(scalar_values=[stale_running, running, queued]),
            _FakeResult(scalar_values=[warning]),
            _FakeResult(scalar_values=[stale_running, running]),
            _FakeResult(scalar_values=[queued]),
            _FakeResult(scalar_values=[reclaimed]),
        ]
    )

    summary = build_jobs_inspection_summary(session, limit=10, now=now)

    assert summary["counts"] == {
        "queued": 1,
        "running": 2,
        "stale_running": 1,
        "failed": 3,
        "completed": 4,
        "warning": 5,
    }
    assert summary["by_status"] == {"completed": 4, "failed": 3, "queued": 1, "running": 2}
    assert summary["ages"] == {
        "longest_running_seconds": 7200,
        "oldest_queued_seconds": 2700,
    }
    assert summary["recent_failed"] == [{"id": 12, "status": "failed"}]
    assert summary["recent_queued_or_running"] == [
        {"id": 14, "status": "running"},
        {"id": 11, "status": "running"},
        {"id": 10, "status": "queued"},
    ]
    assert summary["recent_stale_running"] == [{"id": 14, "status": "running"}]
    assert summary["recent_reclaimed"] == [{"id": 15, "status": "completed"}]
    assert summary["recent_warning"] == [{"id": 13, "status": "completed"}]
