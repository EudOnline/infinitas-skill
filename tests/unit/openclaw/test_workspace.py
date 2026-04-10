from __future__ import annotations

from pathlib import Path

from infinitas_skill.openclaw.contracts import load_openclaw_runtime_profile
from infinitas_skill.openclaw.workspace import resolve_openclaw_skill_dirs

ROOT = Path(__file__).resolve().parents[3]


def test_resolve_openclaw_skill_dirs_prefers_workspace_then_agent_then_user() -> None:
    dirs = resolve_openclaw_skill_dirs(
        Path("/tmp/demo-workspace"),
        home=Path("/Users/tester"),
    )

    assert dirs == [
        Path("/tmp/demo-workspace/skills"),
        Path("/tmp/demo-workspace/.agents/skills"),
        Path("/Users/tester/.agents/skills"),
        Path("/Users/tester/.openclaw/skills"),
    ]


def test_resolve_openclaw_skill_dirs_follows_profile_candidate_order() -> None:
    workspace_root = Path("/tmp/demo-workspace")
    home = Path("/Users/tester")
    profile = load_openclaw_runtime_profile(ROOT)

    dirs = resolve_openclaw_skill_dirs(workspace_root, home=home, root=ROOT)

    expected = []
    for candidate in profile["runtime"]["skill_dir_candidates"]:
        if candidate.startswith("~/"):
            expected.append(home / candidate[2:])
        else:
            expected.append(workspace_root / candidate)

    assert dirs == expected
