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
    readme = ROOT / "README.md"
    consume_skill = ROOT / "skills" / "active" / "consume-infinitas-skill" / "SKILL.md"
    federation_skill = ROOT / "skills" / "active" / "federation-registry-ops" / "SKILL.md"
    cli_reference = ROOT / "docs" / "reference" / "cli-reference.md"
    app_js = ROOT / "server" / "static" / "js" / "app.js"

    for needle in [
        "uv run infinitas discovery search",
        "uv run infinitas discovery recommend",
        "uv run infinitas discovery inspect",
    ]:
        assert_contains(consume_skill, needle)

    for needle in [
        "uv run infinitas discovery search",
        "uv run infinitas discovery inspect",
    ]:
        assert_contains(federation_skill, needle)

    for needle in [
        "infinitas discovery inspect",
        "discovery inspect",
    ]:
        assert_contains(cli_reference, needle)

    assert_contains(readme, "docs/reference/cli-reference.md")
    assert_contains(app_js, "uv run infinitas discovery inspect")

    print("OK: search docs compatibility checks passed")


if __name__ == "__main__":
    main()
