"""Workspace and user skill-directory resolution for OpenClaw."""

from __future__ import annotations

from pathlib import Path

from infinitas_skill.root import ROOT

from .contracts import load_openclaw_runtime_profile


def resolve_openclaw_skill_dirs(
    workspace_root: Path,
    *,
    home: Path | None = None,
    root: Path | None = None,
) -> list[Path]:
    """Resolve canonical skill directory precedence for OpenClaw runtime lookups."""

    workspace_root = Path(workspace_root)
    user_home = Path(home) if home is not None else Path.home()
    profile = load_openclaw_runtime_profile(root or ROOT)
    candidates = list((profile.get("runtime") or {}).get("skill_dir_candidates") or [])

    resolved: list[Path] = []
    for candidate in candidates:
        if candidate.startswith("~/"):
            resolved.append(user_home / candidate[2:])
        elif Path(candidate).is_absolute():
            resolved.append(Path(candidate))
        else:
            resolved.append(workspace_root / candidate)
    return resolved


__all__ = ["resolve_openclaw_skill_dirs"]
