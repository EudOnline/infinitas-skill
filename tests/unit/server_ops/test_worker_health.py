from __future__ import annotations

import os
import time

import pytest

from infinitas_skill.server.worker_health import (
    maintain_worker_heartbeat,
    worker_health_summary,
    write_worker_heartbeat,
)


def test_worker_health_summary_rejects_missing_heartbeat(tmp_path) -> None:
    with pytest.raises(SystemExit, match="1"):
        worker_health_summary(str(tmp_path / "missing"), max_age_seconds=30)


def test_worker_health_summary_rejects_stale_heartbeat(tmp_path) -> None:
    heartbeat = tmp_path / "worker.heartbeat"
    write_worker_heartbeat(str(heartbeat))
    stale = time.time() - 60
    os.utime(heartbeat, (stale, stale))

    with pytest.raises(SystemExit, match="1"):
        worker_health_summary(str(heartbeat), max_age_seconds=30)


def test_maintain_worker_heartbeat_refreshes_during_long_work(tmp_path) -> None:
    heartbeat = tmp_path / "worker.heartbeat"

    with maintain_worker_heartbeat(str(heartbeat), interval_seconds=0.05):
        first_mtime = heartbeat.stat().st_mtime_ns
        time.sleep(0.15)
        assert heartbeat.stat().st_mtime_ns > first_mtime

    assert worker_health_summary(str(heartbeat), max_age_seconds=1)["ok"] is True
