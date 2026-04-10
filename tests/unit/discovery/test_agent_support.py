from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.discovery.agent_support import supports_target_agent
from infinitas_skill.discovery.resolver import resolve_skill
from infinitas_skill.discovery.search import search_skills


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_supports_target_agent_treats_runtime_ready_openclaw_as_compatible() -> None:
    item = {
        "agent_compatible": [],
        "verified_support": {},
        "runtime": {
            "platform": "openclaw",
            "readiness": {"ready": True},
        },
    }

    assert supports_target_agent(item, "openclaw") is True


def test_supports_target_agent_rejects_blocked_openclaw_even_when_runtime_ready() -> None:
    item = {
        "agent_compatible": [],
        "verified_support": {"openclaw": {"state": "blocked"}},
        "runtime": {
            "platform": "openclaw",
            "readiness": {"ready": True},
        },
    }

    assert supports_target_agent(item, "openclaw") is False


def test_search_skills_includes_runtime_ready_openclaw_without_legacy_agent_flag(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "catalog" / "discovery-index.json",
        {
            "skills": [
                {
                    "name": "demo-runtime-skill",
                    "qualified_name": "team/demo-runtime-skill",
                    "publisher": "team",
                    "summary": "OpenClaw-native runtime skill",
                    "latest_version": "1.0.0",
                    "trust_state": "verified",
                    "verified_support": {},
                    "agent_compatible": [],
                    "tags": ["ops"],
                    "attestation_formats": ["ssh"],
                    "source_registry": "self",
                    "runtime": {
                        "platform": "openclaw",
                        "readiness": {"ready": True},
                    },
                }
            ]
        },
    )

    payload = search_skills(tmp_path, query="demo-runtime-skill", agent="openclaw")

    assert [item["qualified_name"] for item in payload["results"]] == ["team/demo-runtime-skill"]


def test_resolve_skill_prefers_runtime_ready_openclaw_candidate_without_legacy_agent_flag() -> None:
    payload = {
        "default_registry": "self",
        "skills": [
            {
                "name": "demo-runtime-skill",
                "qualified_name": "team/demo-runtime-skill",
                "source_registry": "self",
                "default_install_version": "1.0.0",
                "latest_version": "1.0.0",
                "install_requires_confirmation": False,
                "agent_compatible": [],
                "verified_support": {},
                "runtime": {
                    "platform": "openclaw",
                    "readiness": {"ready": True},
                },
            }
        ],
    }

    result = resolve_skill(
        payload=payload,
        query="demo-runtime-skill",
        target_agent="openclaw",
    )

    assert result["state"] == "resolved-private"
    assert (result["resolved"] or {}).get("qualified_name") == "team/demo-runtime-skill"
