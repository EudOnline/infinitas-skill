from __future__ import annotations

import argparse
from pathlib import Path

from infinitas_skill.discovery.install_explanation import (
    build_install_explanation,
    build_resolve_explanation,
)
from infinitas_skill.discovery.resolver import load_discovery_index, resolve_skill
from infinitas_skill.install.common import (
    _emit_payload,
    _repo_root,
)
from infinitas_skill.install.pull import run_pull_skill


def configure_install_resolve_skill_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("query", help="Skill name or qualified_name to resolve")
    parser.add_argument("--target-agent", default=None, help="Optional target runtime/agent")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_resolve_skill_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Resolve one install candidate from the discovery index",
    )
    return configure_install_resolve_skill_parser(parser)


def configure_install_by_name_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("query", help="Skill name or qualified_name to install")
    parser.add_argument("target_dir", help="Target directory for the installed skill")
    parser.add_argument("--version", default=None, help="Optional released version override")
    parser.add_argument("--target-agent", default=None, help="Optional target runtime/agent")
    parser.add_argument(
        "--mode",
        choices=("auto", "confirm"),
        default="auto",
        help="Whether to install immediately or only confirm the plan",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_by_name_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Resolve and install one released skill by discovery-first name lookup",
    )
    return configure_install_by_name_parser(parser)


def _resolve_skill_payload(
    *,
    root: str | Path,
    query: str,
    target_agent: str | None = None,
) -> dict:
    repo_root = _repo_root(str(root))
    try:
        payload = load_discovery_index(repo_root)
        result = resolve_skill(payload=payload, query=query, target_agent=target_agent)
    except Exception as exc:
        result = {
            "ok": False,
            "query": query,
            "state": "failed",
            "resolved": None,
            "candidates": [],
            "requires_confirmation": False,
            "recommended_next_step": "fix discovery-index generation",
            "message": str(exc),
        }

    result["explanation"] = build_resolve_explanation(result)
    return result


def run_install_resolve_skill(
    *,
    root: str | Path,
    query: str,
    target_agent: str | None = None,
    as_json: bool = False,
) -> int:
    payload = _resolve_skill_payload(root=root, query=query, target_agent=target_agent)
    return _emit_payload(payload, as_json=as_json)


def _resolution_failure_details(
    state: str, query: str, target_agent: str | None, resolve_payload: dict
) -> tuple[str, str, str]:
    candidates = resolve_payload.get("candidates") or []
    names = ", ".join(
        candidate.get("qualified_name") or candidate.get("name") or "?"
        for candidate in candidates
        if isinstance(candidate, dict)
    )
    if state == "ambiguous":
        return (
            "ambiguous-skill-name",
            f"ambiguous skill name {query!r}: {names}",
            "choose a qualified_name and rerun infinitas install by-name",
        )
    if state == "not-found":
        return (
            "skill-not-found",
            f"no install candidate found for {query!r}",
            "search discovery-index results or use a known qualified_name",
        )
    if state == "incompatible":
        suffix = f" with target_agent {target_agent!r}" if target_agent else ""
        action = (
            f"pick a skill compatible with {target_agent} or change --target-agent"
            if target_agent
            else "pick a compatible skill before retrying infinitas install by-name"
        )
        return (
            "incompatible-target-agent",
            f"no compatible install candidate for {query!r}{suffix}",
            action,
        )
    return (
        "resolver-failed",
        resolve_payload.get("message") or f"skill resolution failed for {query!r}",
        "fix discovery-index generation or resolver errors and retry",
    )


def _install_result_context(
    *, query: str, resolved: dict, requested_version: str | None, target_dir: str
) -> dict:
    return {
        "query": query,
        "qualified_name": resolved.get("qualified_name"),
        "source_registry": resolved.get("source_registry"),
        "requested_version": requested_version,
        "resolved_version": resolved.get("resolved_version"),
        "target_dir": target_dir,
    }


def _emit_install_explanation(
    resolve_payload: dict, payload: dict, *, requested_version: str | None, as_json: bool
) -> int:
    payload["explanation"] = build_install_explanation(
        resolve_payload, payload, requested_version=requested_version
    )
    return _emit_payload(payload, as_json=as_json)


def run_install_by_name(
    *,
    root: str | Path,
    query: str,
    target_dir: str,
    requested_version: str | None = None,
    target_agent: str | None = None,
    mode: str = "auto",
    as_json: bool = False,
) -> int:
    repo_root = _repo_root(str(root))
    resolve_payload = _resolve_skill_payload(root=repo_root, query=query, target_agent=target_agent)
    state = resolve_payload.get("state") or "failed"
    resolved = resolve_payload.get("resolved") or {}
    context = _install_result_context(
        query=query,
        resolved=resolved,
        requested_version=requested_version,
        target_dir=target_dir,
    )

    if state in {"ambiguous", "not-found", "incompatible", "failed"}:
        error_code, message, suggested_action = _resolution_failure_details(
            state, query, target_agent, resolve_payload
        )
        payload = {
            "ok": False,
            **context,
            "manifest_path": None,
            "state": "failed",
            "requires_confirmation": False,
            "error_code": error_code,
            "message": message,
            "suggested_action": suggested_action,
            "next_step": resolve_payload.get("recommended_next_step") or suggested_action,
        }
        _emit_install_explanation(
            resolve_payload, payload, requested_version=requested_version, as_json=as_json
        )
        return 1

    requires_confirmation = bool(resolve_payload.get("requires_confirmation"))
    if mode == "auto" and requires_confirmation:
        payload = {
            "ok": False,
            **context,
            "manifest_path": None,
            "state": "failed",
            "requires_confirmation": True,
            "error_code": "confirmation-required",
            "next_step": "rerun with --mode confirm and explicit confirmation",
        }
        _emit_install_explanation(
            resolve_payload, payload, requested_version=requested_version, as_json=as_json
        )
        return 1

    qualified_name = resolved.get("qualified_name") or ""
    source_registry = resolved.get("source_registry")
    resolved_version = resolved.get("resolved_version")
    returncode, pull_payload = run_pull_skill(
        repo_root=repo_root,
        qualified_name=qualified_name,
        target_dir=target_dir,
        requested_version=requested_version or resolved_version,
        source_registry=source_registry,
        mode=mode,
    )
    if returncode != 0:
        _emit_payload(pull_payload, as_json=as_json)
        return returncode

    payload = {
        "ok": pull_payload.get("ok"),
        "query": query,
        "qualified_name": pull_payload.get("qualified_name") or qualified_name,
        "source_registry": pull_payload.get("registry_name") or source_registry,
        "requested_version": requested_version or pull_payload.get("requested_version"),
        "resolved_version": pull_payload.get("resolved_version") or resolved_version,
        "target_dir": target_dir,
        "manifest_path": pull_payload.get("lockfile_path") or pull_payload.get("manifest_path"),
        "state": pull_payload.get("state"),
        "requires_confirmation": requires_confirmation,
        "next_step": (
            "check-update-or-use"
            if pull_payload.get("state") == "installed"
            else pull_payload.get("next_step")
        ),
    }
    return _emit_install_explanation(
        resolve_payload,
        payload,
        requested_version=payload.get("requested_version"),
        as_json=as_json,
    )
