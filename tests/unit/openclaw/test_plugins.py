from __future__ import annotations

from infinitas_skill.openclaw.plugins import normalize_plugin_capabilities


def test_normalize_plugin_capabilities_keeps_supported_lists_only() -> None:
    capabilities = normalize_plugin_capabilities(
        {
            "channels": ["chat"],
            "tools": ["shell", "edit"],
            "web_search": ["default"],
            "ignored_flag": True,
            "nested": {"bad": "shape"},
        }
    )

    assert capabilities == {
        "channels": ["chat"],
        "tools": ["shell", "edit"],
        "web_search": ["default"],
    }
