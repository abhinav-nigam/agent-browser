"""Pytest configuration for agent-browser tests."""

import asyncio
import pytest
import pytest_asyncio
from typing import Generator

from agent_browser.mcp import BrowserServer


# Global cache for the shared browser (avoids event loop issues)
_shared_browser: BrowserServer | None = None
_browser_started: bool = False


def get_shared_browser() -> BrowserServer:
    """Get or create the shared browser instance."""
    global _shared_browser
    if _shared_browser is None:
        _shared_browser = BrowserServer("shared-test-browser")
        _shared_browser.configure(allow_private=True, headless=True)
    return _shared_browser


@pytest_asyncio.fixture(scope="session")
async def shared_browser() -> BrowserServer:
    """
    Session-scoped browser instance for all tests.

    This dramatically improves test speed by avoiding browser startup/shutdown
    overhead for each test (1-3 seconds per test).
    """
    global _browser_started
    server = get_shared_browser()
    if not _browser_started:
        await server.start(headless=True)
        _browser_started = True
    yield server
    await server.stop()
    _browser_started = False


# Local test page HTML - avoids network latency from example.com
TEST_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Test Page</h1>
    <p>This is a test paragraph for browser automation tests.</p>
    <div id="content">Content area</div>
</body>
</html>
""".strip()

# Data URL for instant page loads (no network)
TEST_PAGE_DATA_URL = f"data:text/html,{TEST_PAGE_HTML.replace(' ', '%20').replace('<', '%3C').replace('>', '%3E').replace('\"', '%22').replace('#', '%23')}"


@pytest_asyncio.fixture
async def fresh_page(shared_browser: BrowserServer) -> BrowserServer:
    """
    Provides a fresh page state for each test.

    Uses a local data URL for instant loading (no network latency).
    """
    # Use data URL for speed - no network request needed
    await shared_browser.page.goto(TEST_PAGE_DATA_URL)
    # Reset camera and clear any annotations/spotlights
    try:
        await shared_browser.camera_reset(duration_ms=0)
        await shared_browser.clear_annotations()
        await shared_browser.clear_spotlight()
    except Exception:
        pass  # Ignore if these fail
    return shared_browser
