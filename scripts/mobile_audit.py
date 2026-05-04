#!/usr/bin/env python3
"""Capture mobile screenshots for visual audit (authenticated)."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

os.environ["INFINITAS_REGISTRY_API_TOKEN"] = "audit-test-token"
os.environ["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps(["registry-reader-token"])
os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(
    [{"username": "e2e-maintainer", "display_name": "E2E Maintainer", "role": "maintainer", "token": "e2e-maintainer-token"}]
)

# Start dev server
proc = subprocess.Popen(
    [sys.executable, "-c",
     "from server.app import create_app; import uvicorn; uvicorn.run(create_app(), host='127.0.0.1', port=9876, log_level='warning')"],
    cwd=Path(__file__).parent.parent,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for server
for _ in range(30):
    try:
        urllib.request.urlopen("http://127.0.0.1:9876/", timeout=1)
        break
    except Exception:
        time.sleep(0.5)
else:
    proc.terminate()
    raise RuntimeError("Server did not start")

output_dir = Path(__file__).parent.parent / ".state" / "mobile-audit"
output_dir.mkdir(parents=True, exist_ok=True)

pages = [
    ("home", "/?lang=en"),
    ("library", "/library?lang=en"),
    ("settings", "/settings?lang=en"),
    ("activity", "/activity?lang=en"),
    ("shares", "/shares?lang=en"),
    ("access", "/access?lang=en"),
]

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 390, "height": 844})  # iPhone 14
    page = context.new_page()

    # Login first
    page.goto("http://127.0.0.1:9876/login?lang=en", wait_until="networkidle", timeout=15000)
    page.fill("#login-token-input", "e2e-maintainer-token")
    page.click("#login-login-btn")
    page.wait_for_load_state("networkidle")
    time.sleep(0.5)

    for name, path in pages:
        url = f"http://127.0.0.1:9876{path}"
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
            time.sleep(0.3)
            page.screenshot(path=str(output_dir / f"{name}-mobile.png"), full_page=True)
            print(f"✓ {name}: {output_dir / f'{name}-mobile.png'} ({(output_dir / f'{name}-mobile.png').stat().st_size} bytes)")
        except Exception as e:
            print(f"✗ {name}: {e}")

    browser.close()

proc.terminate()
proc.wait(timeout=5)
print(f"\nScreenshots saved to {output_dir}")
