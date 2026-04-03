from __future__ import annotations

from infinitas_skill.server.ops import build_server_render_systemd_parser
from infinitas_skill.server.systemd import (
    render_memory_curation_service,
    render_memory_curation_timer,
)


def test_render_memory_curation_service_and_timer_include_queue_command() -> None:
    parser = build_server_render_systemd_parser()
    args = parser.parse_args(
        [
            "--output-dir",
            "/tmp/out",
            "--repo-root",
            "/srv/infinitas/repo",
            "--python-bin",
            "/srv/infinitas/.venv/bin/python",
            "--env-file",
            "/etc/infinitas/hosted-registry.env",
            "--backup-output-dir",
            "/srv/infinitas/backups",
            "--curation-on-calendar",
            "daily",
            "--curation-action",
            "archive",
            "--curation-max-actions",
            "12",
        ]
    )

    service = render_memory_curation_service(args)
    timer = render_memory_curation_timer(args)

    assert "server memory-curation" in service
    assert "--enqueue" in service
    assert "--use-server-policy" in service
    assert "--action archive" not in service
    assert "--max-actions 12" not in service
    assert "OnCalendar=daily" in timer
