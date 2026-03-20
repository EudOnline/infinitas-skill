#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def assert_contains(path: str, needle: str) -> None:
    if needle not in read(path):
        fail(f"expected {path} to contain {needle!r}")


def assert_not_contains(path: str, needle: str) -> None:
    if needle in read(path):
        fail(f"expected {path} not to contain {needle!r}")


REQUIRED = {
    ".planning/PROJECT.md": [
        "v20 is complete on `main`.",
        "The project is now in steady-state unless a new milestone is intentionally started.",
    ],
    ".planning/REQUIREMENTS.md": [
        "All v20 requirements are complete on `main`.",
        "Future work should be opened as a new milestone or maintenance slice.",
    ],
    ".planning/ROADMAP.md": [
        "The project is complete on `main` and now operates in steady-state.",
    ],
    ".planning/STATE.md": [
        "**Current focus:** project complete on `main`, no active milestone.",
        "Phase: steady-state",
        "Status: v20 complete on `main`; the repository is in steady-state until a new milestone is intentionally opened",
    ],
    "docs/project-closeout.md": [
        "The current `infinitas-skill` project is complete on `main`.",
        "Future work belongs to a new milestone or maintenance slice, not unfinished v20 scope.",
    ],
}


FORBIDDEN = {
    ".planning/PROJECT.md": [
        "the remaining operational step is to merge the branch back to `main`",
    ],
    ".planning/REQUIREMENTS.md": [
        "the remaining operational step is merging the verified branch back to `main`",
    ],
    ".planning/ROADMAP.md": [
        "The next operational step is to merge `codex/v17-installed-reporting` back to `main`; no v21 milestone is committed yet.",
    ],
    ".planning/STATE.md": [
        "fresh verification evidence plus merge-back to `main`",
        "Phase: v20 closeout complete, merge prep",
        "Merge `codex/v17-installed-reporting` back to `main` with fresh v20 verification evidence.",
        "Stopped at: v20 closeout implementation complete on `codex/v17-installed-reporting`; next step is fresh verification and merge-back to `main`",
    ],
    "docs/project-closeout.md": [
        "## Merge Gates",
        "The branch is ready to merge only when all of the following are true:",
        "The current project phase can be treated as complete when:",
        "The branch has been merged back to `main`.",
    ],
}


def main() -> None:
    planning_paths = [
        ROOT / ".planning/PROJECT.md",
        ROOT / ".planning/REQUIREMENTS.md",
        ROOT / ".planning/ROADMAP.md",
        ROOT / ".planning/STATE.md",
    ]
    if all(not path.exists() for path in planning_paths):
        print("SKIP: project complete state checks (planning docs unavailable in this workspace copy)")
        return
    for path, needles in REQUIRED.items():
        for needle in needles:
            assert_contains(path, needle)
    for path, needles in FORBIDDEN.items():
        for needle in needles:
            assert_not_contains(path, needle)
    print("OK: project complete state checks passed")


if __name__ == "__main__":
    main()
