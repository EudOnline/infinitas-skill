"""Semantic-version parsing and dependency constraint evaluation."""

from __future__ import annotations

import re

from typing_extensions import TypedDict

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)
COMPARATOR_RE = re.compile(r"^(<=|>=|<|>|=)?(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?)$")

PrereleasePart = int | str


class SemVer(TypedDict):
    major: int
    minor: int
    patch: int
    prerelease: tuple[PrereleasePart, ...]


def parse_semver(version: str) -> SemVer:
    match = SEMVER_RE.match(version or "")
    if not match:
        raise ValueError(f"invalid semver: {version!r}")
    prerelease_parts: list[PrereleasePart] = []
    if prerelease := match.group(4):
        prerelease_parts.extend(
            int(part) if part.isdigit() else part for part in prerelease.split(".")
        )
    return {
        "major": int(match.group(1)),
        "minor": int(match.group(2)),
        "patch": int(match.group(3)),
        "prerelease": tuple(prerelease_parts),
    }


def compare_prerelease(left: tuple[PrereleasePart, ...], right: tuple[PrereleasePart, ...]) -> int:
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for left_item, right_item in zip(left, right):
        if left_item == right_item:
            continue
        if isinstance(left_item, int) and isinstance(right_item, int):
            return -1 if left_item < right_item else 1
        if isinstance(left_item, int):
            return -1
        if isinstance(right_item, int):
            return 1
        return -1 if left_item < right_item else 1
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def compare_versions(left: str, right: str) -> int:
    left_semver = parse_semver(left)
    right_semver = parse_semver(right)
    left_core = (left_semver["major"], left_semver["minor"], left_semver["patch"])
    right_core = (right_semver["major"], right_semver["minor"], right_semver["patch"])
    if left_core != right_core:
        return -1 if left_core < right_core else 1
    return compare_prerelease(left_semver["prerelease"], right_semver["prerelease"])


def caret_upper_bound(version: str) -> str:
    parsed = parse_semver(version)
    if parsed["major"] > 0:
        return f"{parsed['major'] + 1}.0.0"
    if parsed["minor"] > 0:
        return f"0.{parsed['minor'] + 1}.0"
    return f"0.0.{parsed['patch'] + 1}"


def tilde_upper_bound(version: str) -> str:
    parsed = parse_semver(version)
    return f"{parsed['major']}.{parsed['minor'] + 1}.0"


def parse_constraint_expression(expression: str | None) -> list[tuple[str, str]]:
    expr = (expression or "*").strip()
    if not expr or expr == "*":
        return []
    comparators: list[tuple[str, str]] = []
    for token in expr.replace(",", " ").split():
        if token == "*":
            continue
        if token.startswith("^"):
            base = token[1:]
            parse_semver(base)
            comparators.extend(((">=", base), ("<", caret_upper_bound(base))))
            continue
        if token.startswith("~"):
            base = token[1:]
            parse_semver(base)
            comparators.extend(((">=", base), ("<", tilde_upper_bound(base))))
            continue
        match = COMPARATOR_RE.match(token)
        if not match:
            raise ValueError(f"invalid version constraint token: {token!r}")
        version = match.group(2)
        parse_semver(version)
        comparators.append((match.group(1) or "=", version))
    return comparators


def canonicalize_constraint(expression: str | None) -> str:
    comparators = parse_constraint_expression((expression or "*").strip())
    return " ".join(f"{op}{version}" for op, version in comparators) or "*"


def constraint_is_exact(expression: str | None) -> bool:
    comparators = parse_constraint_expression(expression)
    return len(comparators) == 1 and comparators[0][0] == "="


def version_satisfies(version: str, expression: str | None) -> bool:
    for op, bound in parse_constraint_expression(expression):
        comparison = compare_versions(version, bound)
        if (op == "=" and comparison != 0) or (op == ">" and comparison <= 0):
            return False
        if (op == ">=" and comparison < 0) or (op == "<" and comparison >= 0):
            return False
        if op == "<=" and comparison > 0:
            return False
    return True
