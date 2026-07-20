"""Heartbeat helpers for the hosted background worker."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infinitas_skill.server.repo_checks import fail


def write_worker_heartbeat(path: str) -> None:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")


@contextmanager
def maintain_worker_heartbeat(path: str, *, interval_seconds: float = 10.0) -> Iterator[None]:
    """Refresh a worker heartbeat independently of queue and job duration."""
    write_worker_heartbeat(path)
    stopped = threading.Event()

    def refresh() -> None:
        while not stopped.wait(max(interval_seconds, 0.1)):
            write_worker_heartbeat(path)

    thread = threading.Thread(target=refresh, name="worker-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=max(interval_seconds, 0.1) + 1.0)
        write_worker_heartbeat(path)


def worker_health_summary(path: str, *, max_age_seconds: int) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        fail(f"worker heartbeat is missing: {target}")
    age_seconds = max(datetime.now(timezone.utc).timestamp() - target.stat().st_mtime, 0.0)
    if age_seconds > max_age_seconds:
        fail(f"worker heartbeat is stale: {age_seconds:.1f}s > {max_age_seconds}s at {target}")
    return {"ok": True, "path": str(target), "age_seconds": round(age_seconds, 3)}


def run_worker_healthcheck(
    *,
    health_path: str,
    max_age_seconds: int,
    as_json: bool = False,
) -> int:
    summary = worker_health_summary(health_path, max_age_seconds=max_age_seconds)
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"OK: worker heartbeat {summary['path']} age_seconds={summary['age_seconds']}")
    return 0


__all__ = [
    "maintain_worker_heartbeat",
    "run_worker_healthcheck",
    "worker_health_summary",
    "write_worker_heartbeat",
]
