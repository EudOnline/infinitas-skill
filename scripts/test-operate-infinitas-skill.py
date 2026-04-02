#!/usr/bin/env python3
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "active" / "operate-infinitas-skill"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def load_json(path: Path):
    try:
        return json.loads(read(path))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        fail(f"missing {label}: expected to find {needle!r}")


def main() -> None:
    if not SKILL_DIR.is_dir():
        fail(f"missing active operate skill directory: {SKILL_DIR}")

    skill_md = read(SKILL_DIR / "SKILL.md")
    meta = load_json(SKILL_DIR / "_meta.json")
    smoke = read(SKILL_DIR / "tests" / "smoke.md")

    for section in [
        "## Shared Model",
        "## OpenClaw",
        "## Codex",
        "## Claude Code",
        "## Hard Rules",
    ]:
        assert_contains(skill_md, section, f"{section} section")

    for phrase in [
        "private-first infinitas-skill registry",
        "drafts, releases, exposures, review cases",
        "Do not use removed publish/promotion shell scripts",
    ]:
        assert_contains(skill_md, phrase, phrase)

    if meta.get("name") != "operate-infinitas-skill":
        fail(f"expected operate skill name, got {meta.get('name')!r}")
    if meta.get("publisher") != "lvxiaoer":
        fail(f"expected publisher 'lvxiaoer', got {meta.get('publisher')!r}")
    if meta.get("qualified_name") != "lvxiaoer/operate-infinitas-skill":
        fail(f"unexpected qualified_name: {meta.get('qualified_name')!r}")
    if meta.get("status") != "active":
        fail(f"expected active status, got {meta.get('status')!r}")
    if meta.get("maturity") != "stable":
        fail(f"expected stable maturity, got {meta.get('maturity')!r}")
    if meta.get("quality_score") != 90:
        fail(f"expected quality_score 90, got {meta.get('quality_score')!r}")

    required_agents = {"openclaw", "claude", "claude-code", "codex"}
    actual_agents = set(meta.get("agent_compatible") or [])
    missing_agents = required_agents - actual_agents
    if missing_agents:
        fail(f"missing agent compatibility entries: {sorted(missing_agents)!r}")

    required_capabilities = {"repo-operations", "release-guidance", "registry-debugging"}
    actual_capabilities = set(meta.get("capabilities") or [])
    missing_capabilities = required_capabilities - actual_capabilities
    if missing_capabilities:
        fail(f"missing operate skill capabilities: {sorted(missing_capabilities)!r}")

    tests = meta.get("tests") or {}
    if tests.get("smoke") != "tests/smoke.md":
        fail(f"expected tests.smoke to point at tests/smoke.md, got {tests.get('smoke')!r}")

    for phrase in [
        "private-first lifecycle stages",
        "uv run infinitas registry",
        "/api/v1/install/*",
        "/registry/*",
    ]:
        assert_contains(smoke, phrase, f"smoke guidance {phrase}")

    print("OK: operate-infinitas-skill compatibility checks passed")


if __name__ == "__main__":
    main()
