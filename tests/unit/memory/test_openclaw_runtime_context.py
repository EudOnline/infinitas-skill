from __future__ import annotations

from infinitas_skill.memory.context import (
    build_inspect_memory_query,
    build_recommendation_memory_query,
)
from infinitas_skill.server.ops import build_server_render_systemd_parser
from infinitas_skill.server.systemd import render_memory_curation_service


def test_recommendation_memory_query_can_capture_openclaw_runtime_context() -> None:
    query = build_recommendation_memory_query(
        task="install released skill into openclaw workspace",
        target_agent="openclaw",
        runtime_platform="openclaw",
        user_ref="maintainer",
        workspace_root="/srv/workspaces/demo",
        session_ref="session-42",
        task_capabilities=["background-task", "workspace-state"],
        runtime_capabilities=["supports_background_tasks", "supports_subagents"],
    )

    assert query.scope_refs == [
        "user:maintainer",
        "agent:openclaw",
        "workspace:/srv/workspaces/demo",
        "session:session-42",
        "task:install",
        "capability:background-task",
        "capability:workspace-state",
    ]
    assert query.provider_scope == {
        "user_ref": "maintainer",
        "agent_id": "openclaw",
        "task_ref": "install",
        "workspace_root": "/srv/workspaces/demo",
        "session_ref": "session-42",
        "runtime_platform": "openclaw",
        "task_capabilities": ["background-task", "workspace-state"],
        "runtime_capabilities": ["supports_background_tasks", "supports_subagents"],
    }


def test_inspect_memory_query_can_capture_runtime_context_without_losing_skill_scope() -> None:
    query = build_inspect_memory_query(
        skill_ref="team/runtime-aware",
        target_agent="openclaw",
        runtime_platform="openclaw",
        user_ref="maintainer",
        workspace_root="/srv/workspaces/demo",
        session_ref="inspect-9",
        task="inspect runtime readiness",
        task_capabilities=["workspace-state"],
        runtime_capabilities=["supports_plugins"],
        extra_scope_refs=["workspace:/srv/workspaces/demo", "session:inspect-9"],
    )

    assert query.scope_refs == [
        "user:maintainer",
        "agent:openclaw",
        "skill:team/runtime-aware",
        "workspace:/srv/workspaces/demo",
        "session:inspect-9",
        "task:inspect",
        "capability:workspace-state",
    ]
    assert query.provider_scope == {
        "user_ref": "maintainer",
        "agent_id": "openclaw",
        "skill_ref": "team/runtime-aware",
        "task_ref": "inspect",
        "workspace_root": "/srv/workspaces/demo",
        "session_ref": "inspect-9",
        "runtime_platform": "openclaw",
        "task_capabilities": ["workspace-state"],
        "runtime_capabilities": ["supports_plugins"],
    }


def test_memory_curation_service_uses_runtime_background_task_vocabulary() -> None:
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
        ]
    )

    service = render_memory_curation_service(args)

    assert "OpenClaw Runtime Memory Maintenance Background Task Enqueue" in service
    assert "server memory-curation --database-url" in service
    assert "--use-server-policy --enqueue --json" in service
