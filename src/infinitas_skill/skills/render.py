"""Render canonical skills for supported platforms."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, cast

from .canonical import load_skill_source

TOOL_INTENT_MAPPINGS = {
    "claude": {
        "plan_tracking": "TodoWrite",
        "subagent_dispatch": "Task",
        "shell_execution": "Bash",
        "file_read": "Read",
        "file_write": "Write/Edit",
    },
    "codex": {
        "plan_tracking": "update_plan",
        "subagent_dispatch": "spawn_agent",
        "shell_execution": "shell",
        "file_read": "file tool",
        "file_write": "file tool",
    },
    "openclaw": {
        "plan_tracking": "agent-managed planning",
        "subagent_dispatch": "not-native",
        "shell_execution": "shell",
        "file_read": "file access",
        "file_write": "file access",
    },
}


class RenderSkillError(Exception):
    pass


def load_platform_profile(root: Path, platform: str) -> dict:
    profile_path = root / "profiles" / f"{platform}.json"
    if not profile_path.is_file():
        raise RenderSkillError(f"missing platform profile: {profile_path}")
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RenderSkillError(f"invalid JSON in {profile_path}: {exc}") from exc
    if payload.get("platform") != platform:
        raise RenderSkillError(
            f"platform profile {profile_path} has mismatched platform {payload.get('platform')!r}"
        )
    return cast(dict[Any, Any], payload)


def apply_tool_intent_mapping(source: dict, platform: str, profile: dict) -> dict:
    mapping = dict(TOOL_INTENT_MAPPINGS.get(platform, {}))
    return {
        "profile_platform": profile.get("platform"),
        "required": {
            intent: mapping.get(intent, intent)
            for intent in source.get("tool_intents", {}).get("required", [])
        },
        "optional": {
            intent: mapping.get(intent, intent)
            for intent in source.get("tool_intents", {}).get("optional", [])
        },
    }


def render_skill_markdown(source: dict, platform: str, profile: dict) -> str:
    frontmatter = [
        "---",
        f"name: {source.get('name')}",
        f"description: {source.get('description')}",
    ]
    frontmatter.append("---")
    body = Path(source["instructions_body_path"]).read_text(encoding="utf-8").rstrip()
    mappings = apply_tool_intent_mapping(source, platform, profile)
    mapping_lines = []
    if mappings["required"] or mappings["optional"]:
        mapping_lines.extend(["", "## Platform Tool Mapping"])
        if mappings["required"]:
            mapping_lines.append("")
            mapping_lines.append("Required intents:")
            for intent, mapped in mappings["required"].items():
                mapping_lines.append(f"- `{intent}` -> `{mapped}`")
        if mappings["optional"]:
            mapping_lines.append("")
            mapping_lines.append("Optional intents:")
            for intent, mapped in mappings["optional"].items():
                mapping_lines.append(f"- `{intent}` -> `{mapped}`")
    return (
        "\n".join(frontmatter)
        + "\n\n"
        + body
        + ("\n" + "\n".join(mapping_lines) if mapping_lines else "")
        + "\n"
    )


def _copy_support_dir(source_dir: Path, target_dir: Path, name: str) -> list[str]:
    src = source_dir / name
    if not src.exists():
        return []
    dest = target_dir / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return [str(path.relative_to(target_dir)) for path in sorted(dest.rglob("*")) if path.is_file()]


def _emit_platform_files(source: dict, platform: str, out_dir: Path) -> list[str]:
    overrides = (source.get("platform_overrides") or {}).get(platform) or {}
    files: list[str] = []
    if platform == "claude" and overrides.get("command_wrapper_name"):
        commands_dir = out_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        wrapper = commands_dir / f"{overrides['command_wrapper_name']}.md"
        wrapper.write_text(
            "---\n"
            f'description: "Wrapper for {source.get("name")}"\n'
            "---\n\n"
            f"Use the `{source.get('name')}` skill when this command is invoked.\n",
            encoding="utf-8",
        )
        files.append(str(wrapper.relative_to(out_dir)))
    if platform == "codex" and overrides.get("emit_openai_yaml"):
        agents_dir = out_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        openai_yaml = agents_dir / "openai.yaml"
        openai_yaml.write_text(
            f"name: {source.get('name')}\n"
            f"description: {source.get('description')}\n"
            "entrypoint: SKILL.md\n",
            encoding="utf-8",
        )
        files.append(str(openai_yaml.relative_to(out_dir)))
    if platform == "codex" and overrides.get("emit_agents_md_snippet"):
        agents_md = out_dir / "AGENTS.md"
        agents_md.write_text(
            "# Codex Skill Bootstrap\n\n"
            f"Load `{source.get('name')}` from `.agents/skills/{source.get('name')}` "
            "when its trigger conditions match.\n",
            encoding="utf-8",
        )
        files.append(str(agents_md.relative_to(out_dir)))
    return files


def render_skill(source: dict, platform: str, out_dir: Path, profile: dict) -> dict:
    out_dir = Path(out_dir).resolve()
    source_dir = Path(source["source_dir"]).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for dirname in ["references", "assets", "scripts"]:
        files.extend(_copy_support_dir(source_dir, out_dir, dirname))
    skill_md = render_skill_markdown(source, platform, profile)
    (out_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
    files.extend(_emit_platform_files(source, platform, out_dir))
    files = ["SKILL.md"] + sorted({item for item in files if item != "SKILL.md"})
    return {
        "platform": platform,
        "profile_version": (profile.get("contract") or {}).get("last_verified"),
        "out_dir": str(out_dir),
        "files": files,
    }


def render_skill_from_dir(root: Path, skill_dir: Path, platform: str, out_dir: Path) -> dict:
    source = load_skill_source(skill_dir)
    profile = load_platform_profile(root, platform)
    return render_skill(source=source, platform=platform, out_dir=out_dir, profile=profile)


__all__ = [
    "RenderSkillError",
    "TOOL_INTENT_MAPPINGS",
    "load_platform_profile",
    "apply_tool_intent_mapping",
    "render_skill_markdown",
    "render_skill",
    "render_skill_from_dir",
]
