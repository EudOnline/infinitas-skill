from server.ui.console import (
    build_console_context,
    build_console_forbidden_context,
    build_lifecycle_console_context,
)
from server.ui.home import build_home_context
from server.ui.navigation import build_site_nav
from server.ui.routes import register_ui_routes

__all__ = [
    "build_console_context",
    "build_console_forbidden_context",
    "build_home_context",
    "build_lifecycle_console_context",
    "build_site_nav",
    "register_ui_routes",
]
