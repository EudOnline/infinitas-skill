from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _rule(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\n\s*\}}", css, re.DOTALL)
    assert match is not None, f"missing CSS rule for {selector}"
    return match.group("body")


def test_control_plane_surfaces_are_quiet_while_hero_keeps_brand_emphasis() -> None:
    css = (ROOT / "server/static/css/input.css").read_text(encoding="utf-8")
    hero = (ROOT / "server/templates/partials/home-hero.html").read_text(encoding="utf-8")

    assert 'class="hero-card ' in hero

    card = _rule(css, ".kawaii-card")
    assert "background: var(--kawaii-surface-elevated);" in card
    assert "border: 1px solid var(--kawaii-line);" in card

    card_accent = _rule(css, ".kawaii-card::before")
    assert "display: none;" in card_accent

    hero_card = _rule(css, ".hero-card")
    assert "background: var(--gradient-card);" in hero_card
    hero_accent = _rule(css, ".hero-card::before")
    assert "display: block;" in hero_accent

    for selector in (".topbar", ".search-dropdown", ".user-panel", ".auth-modal-backdrop"):
        assert "backdrop-filter" not in _rule(css, selector)

    for selector in (
        'html[data-color-scheme="dark"] .toast--success',
        'html[data-color-scheme="dark"] .toast--error',
        'html[data-color-scheme="dark"] .toast--warning',
        'html[data-color-scheme="dark"] .toast--info',
        'html[data-color-scheme="dark"] .kawaii-badge--success',
        'html[data-color-scheme="dark"] .kawaii-badge--pending',
        'html[data-color-scheme="dark"] .kawaii-badge--running',
        'html[data-color-scheme="dark"] .kawaii-badge--error',
    ):
        assert "box-shadow" not in _rule(css, selector)
