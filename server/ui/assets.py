"""Static asset versioning helpers.

Build pipeline writes ``server/static/.hashes.json``; this module
reads it and exposes a Jinja2 global so templates can append
content hashes to static URLs for cache busting.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_asset_hashes(static_dir: Path) -> dict[str, str]:
    """Load the asset hash manifest, returning an empty dict on any error."""
    manifest = static_dir / ".hashes.json"
    try:
        return json.loads(manifest.read_text())
    except Exception:
        logger.debug("asset hash manifest not found or invalid: %s", manifest)
        return {}


def static_url_factory(hashes: dict[str, str]):
    """Return a ``static_url(path)`` function for Jinja2 templates.

    ``path`` must start with ``/static/``.  If a matching hash is found
    in *hashes*, the returned URL includes a ``?v=<hash>`` query string.
    """

    def static_url(path: str) -> str:
        key = path.removeprefix("/static/").lstrip("/")
        h = hashes.get(key)
        return f"{path}?v={h}" if h else path

    return static_url
