"""Package-owned discovery CLI surface."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from infinitas_skill.discovery.inspect import inspect_skill
from infinitas_skill.discovery.recommendation import recommend_skills
from infinitas_skill.discovery.search import search_skills
from infinitas_skill.server.memory_retrieval_audit import build_memory_retrieval_audit_recorder

DISCOVERY_TOP_LEVEL_HELP = "Discovery and inspection tools"
DISCOVERY_PARSER_DESCRIPTION = "Discovery, recommendation, and inspection CLI"


def _repo_root(value: str | None) -> Path:
    return Path(value or ".").resolve()


def _emit_payload(payload: dict, *, as_json: bool) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if as_json else None))
    return 0


def _audit_recorder(default_actor_ref: str):
    database_url = os.environ.get("INFINITAS_DISCOVERY_AUDIT_DATABASE_URL", "").strip()
    actor_ref = os.environ.get("INFINITAS_DISCOVERY_AUDIT_ACTOR_REF", default_actor_ref).strip()
    if not database_url:
        return None
    return build_memory_retrieval_audit_recorder(database_url=database_url, actor_ref=actor_ref)


def run_discovery_search(
    *,
    root: str | Path,
    query: str | None = None,
    publisher: str | None = None,
    agent: str | None = None,
    tag: str | None = None,
    as_json: bool = False,
) -> int:
    payload = search_skills(
        _repo_root(str(root)),
        query=query,
        publisher=publisher,
        agent=agent,
        tag=tag,
    )
    return _emit_payload(payload, as_json=as_json)


def run_discovery_recommend(
    *,
    root: str | Path,
    task: str,
    target_agent: str | None = None,
    limit: int = 5,
    as_json: bool = False,
) -> int:
    payload = recommend_skills(
        _repo_root(str(root)),
        task=task,
        target_agent=target_agent,
        limit=limit,
        audit_recorder=_audit_recorder("system:discovery:recommend-cli"),
    )
    return _emit_payload(payload, as_json=as_json)


def run_discovery_inspect(
    *,
    root: str | Path,
    name: str,
    version: str | None = None,
    target_agent: str | None = None,
    as_json: bool = False,
) -> int:
    payload = inspect_skill(
        _repo_root(str(root)),
        name=name,
        version=version,
        target_agent=target_agent,
        audit_recorder=_audit_recorder("system:discovery:inspect-cli"),
    )
    return _emit_payload(payload, as_json=as_json)


def build_discovery_search_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Search generated discovery surfaces")
    configure_discovery_search_parser(parser)
    return parser


def configure_discovery_search_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("query", nargs="?", default=None, help="Optional search query")
    parser.add_argument("--publisher", default=None, help="Filter by publisher")
    parser.add_argument("--agent", default=None, help="Filter by target agent")
    parser.add_argument("--tag", default=None, help="Filter by tag")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_discovery_recommend_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Recommend the best matching skill")
    configure_discovery_recommend_parser(parser)
    return parser


def configure_discovery_recommend_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("task", help="Task or intent to rank against the discovery index")
    parser.add_argument("--target-agent", default=None, help="Optional target runtime/agent")
    parser.add_argument("--limit", type=int, default=5, help="Maximum ranked results to emit")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_discovery_inspect_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Inspect one released skill")
    configure_discovery_inspect_parser(parser)
    return parser


def configure_discovery_inspect_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("name", help="Qualified name or skill name")
    parser.add_argument("--version", default=None, help="Optional version override")
    parser.add_argument("--target-agent", default=None, help="Optional target runtime/agent")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def configure_discovery_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(
        dest="discovery_command",
        metavar="{search,recommend,inspect}",
    )

    search = subparsers.add_parser("search", help="Search generated discovery surfaces")
    configure_discovery_search_parser(search)
    search.set_defaults(
        _handler=lambda args: run_discovery_search(
            root=args.repo_root,
            query=args.query,
            publisher=args.publisher,
            agent=args.agent,
            tag=args.tag,
            as_json=args.json,
        )
    )

    recommend = subparsers.add_parser("recommend", help="Recommend the best matching skill")
    configure_discovery_recommend_parser(recommend)
    recommend.set_defaults(
        _handler=lambda args: run_discovery_recommend(
            root=args.repo_root,
            task=args.task,
            target_agent=args.target_agent,
            limit=args.limit,
            as_json=args.json,
        )
    )

    inspect = subparsers.add_parser("inspect", help="Inspect one released skill")
    configure_discovery_inspect_parser(inspect)
    inspect.set_defaults(
        _handler=lambda args: run_discovery_inspect(
            root=args.repo_root,
            name=args.name,
            version=args.version,
            target_agent=args.target_agent,
            as_json=args.json,
        )
    )

    return parser


def build_discovery_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description=DISCOVERY_PARSER_DESCRIPTION)
    return configure_discovery_parser(parser)


__all__ = [
    "DISCOVERY_PARSER_DESCRIPTION",
    "DISCOVERY_TOP_LEVEL_HELP",
    "build_discovery_inspect_parser",
    "build_discovery_parser",
    "build_discovery_recommend_parser",
    "build_discovery_search_parser",
    "configure_discovery_inspect_parser",
    "configure_discovery_parser",
    "configure_discovery_recommend_parser",
    "configure_discovery_search_parser",
    "run_discovery_inspect",
    "run_discovery_recommend",
    "run_discovery_search",
]
