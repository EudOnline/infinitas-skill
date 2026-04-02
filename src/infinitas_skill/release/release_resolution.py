"""Deterministic release resolution helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinitas_skill.release.git_state import ReleaseError


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_skill(root: str | Path, target: str | Path) -> Path:
    candidate = Path(target)
    if candidate.is_dir() and (candidate / "_meta.json").exists():
        return candidate.resolve()
    for stage in ["active", "incubating", "archived"]:
        skill_dir = Path(root) / "skills" / stage / str(target)
        if skill_dir.is_dir() and (skill_dir / "_meta.json").exists():
            return skill_dir.resolve()
    raise ReleaseError(f"cannot resolve skill: {target}")


def expected_skill_tag(skill_dir: str | Path) -> tuple[dict[str, Any], str]:
    meta = load_json(Path(skill_dir) / "_meta.json")
    return meta, f"skill/{meta['name']}/v{meta['version']}"


def build_review_payload(
    review_entries: list[dict[str, Any]],
    review_evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"reviewers": review_entries}
    if review_evaluation:
        payload.update(
            {
                "effective_review_state": review_evaluation.get("effective_review_state"),
                "required_approvals": review_evaluation.get("required_approvals"),
                "required_groups": review_evaluation.get("required_groups", []),
                "covered_groups": review_evaluation.get("covered_groups", []),
                "missing_groups": review_evaluation.get("missing_groups", []),
                "approval_count": review_evaluation.get("approval_count"),
                "blocking_rejection_count": review_evaluation.get("blocking_rejection_count"),
                "quorum_met": review_evaluation.get("quorum_met"),
                "review_gate_pass": review_evaluation.get("review_gate_pass"),
                "latest_decisions": review_evaluation.get("latest_decisions", []),
                "ignored_decisions": review_evaluation.get("ignored_decisions", []),
                "configured_groups": review_evaluation.get("configured_groups", {}),
            }
        )
    return payload


__all__ = [
    "build_review_payload",
    "expected_skill_tag",
    "load_json",
    "resolve_skill",
]
