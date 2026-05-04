from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from src.infinitas_skill.compatibility.contracts import (
    extract_section,
    validate_platform_contract,
)


class TestExtractSection:
    def test_extracts_section(self):
        text = "# Title\n## Section A\ncontent a\n## Section B\ncontent b"
        assert extract_section(text, "## Section A") == "content a"

    def test_missing_section(self):
        text = "# Title\n## Section A\ncontent a"
        assert extract_section(text, "## Missing") == ""

    def test_empty_section(self):
        text = "# Title\n## Section A\n\n## Section B\ncontent"
        assert extract_section(text, "## Section A") == ""


class TestValidatePlatformContract:
    def test_valid_contract(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "contract.md"
            path.write_text(
                "# Test Contract\n"
                "## Stable assumptions\nassumptions\n"
                "## Volatile assumptions\nvolatile\n"
                "## Official sources\nhttps://example.com\n"
                "## Last verified\n2026-04-01\n"
                "## Verification steps\nsteps\n"
                "## Known gaps\ngaps\n",
                encoding="utf-8",
            )
            payload, errors = validate_platform_contract(path, "Test Contract")
            assert not errors
            assert payload["last_verified"].year == 2026

    def test_missing_file(self):
        payload, errors = validate_platform_contract(Path("/nonexistent"), "Title")
        assert any("missing" in e for e in errors)

    def test_missing_title(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "contract.md"
            path.write_text(
                "## Stable assumptions\n"
                "## Volatile assumptions\n"
                "## Official sources\nhttps://example.com\n"
                "## Last verified\n2026-04-01\n"
                "## Verification steps\n"
                "## Known gaps\n",
                encoding="utf-8",
            )
            payload, errors = validate_platform_contract(path, "Wrong Title")
            assert any("missing required title" in e for e in errors)

    def test_missing_heading(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "contract.md"
            path.write_text(
                "# Title\n## Official sources\nhttps://example.com\n## Last verified\n2026-04-01\n",
                encoding="utf-8",
            )
            payload, errors = validate_platform_contract(path, "Title")
            assert any("missing required heading" in e for e in errors)

    def test_bad_date(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "contract.md"
            path.write_text(
                "# Title\n"
                "## Stable assumptions\n"
                "## Volatile assumptions\n"
                "## Official sources\nhttps://example.com\n"
                "## Last verified\nnot-a-date\n"
                "## Verification steps\n"
                "## Known gaps\n",
                encoding="utf-8",
            )
            payload, errors = validate_platform_contract(path, "Title")
            assert any("could not parse" in e or "invalid" in e for e in errors)

    def test_no_urls(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "contract.md"
            path.write_text(
                "# Title\n"
                "## Stable assumptions\n"
                "## Volatile assumptions\n"
                "## Official sources\n"
                "## Last verified\n2026-04-01\n"
                "## Verification steps\n"
                "## Known gaps\n",
                encoding="utf-8",
            )
            payload, errors = validate_platform_contract(path, "Title")
            assert any("HTTPS source URL" in e for e in errors)
