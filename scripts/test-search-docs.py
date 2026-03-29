#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"missing documentation file: {path}")
    return path.read_text(encoding="utf-8")


def assert_contains(path: Path, needle: str) -> None:
    if needle not in read(path):
        fail(f"expected {path} to mention {needle!r}")


def main() -> None:
    search_doc = ROOT / "docs" / "ai" / "search-and-inspect.md"
    recommend_doc = ROOT / "docs" / "ai" / "recommend.md"
    pull_doc = ROOT / "docs" / "ai" / "pull.md"

    for needle in [
        "scripts/search-skills.sh",
        "scripts/recommend-skill.sh",
        "scripts/inspect-skill.sh",
        "install-by-name.sh",
        "upgrade-skill.sh",
        "trust state",
        "provenance",
        "verified distribution manifests",
        "comparison_summary",
    ]:
        assert_contains(search_doc, needle)

    for needle in [
        "scripts/recommend-skill.sh",
        "scripts/search-skills.sh",
        "scripts/inspect-skill.sh",
        "trust state",
        "compatibility",
        "maturity",
        "verification freshness",
        "confidence",
        "comparative_signals",
        "comparison_summary",
    ]:
        assert_contains(recommend_doc, needle)

    for needle in [
        "provenance",
        "signature",
        "/registry/provenance/",
    ]:
        assert_contains(pull_doc, needle)

    print("OK: search docs compatibility checks passed")


if __name__ == "__main__":
    main()
