"""Tests for MCP server functionality."""

import pytest
import asyncio
from pathlib import Path
from agent_browser.mcp import validate_url, MCPDriver, BrowserErrorCode

class TestURLValidation:
    def test_valid_urls(self):
        assert validate_url("http://google.com") == "http://google.com"
        assert validate_url("https://github.com/abhinav-nigam/agent-browser") == "https://github.com/abhinav-nigam/agent-browser"

    def test_blocked_schemes(self):
        with pytest.raises(ValueError, match="Forbidden scheme: file"):
            validate_url("file:///etc/passwd")
        with pytest.raises(ValueError, match="Forbidden scheme: data"):
            validate_url("data:text/html,<h1>Hacked</h1>")
        with pytest.raises(ValueError, match="Forbidden scheme: javascript"):
            validate_url("javascript:alert(1)")

    def test_blocked_private_ips(self):
        with pytest.raises(ValueError, match="blocked"):
            validate_url("http://192.168.1.1")
        with pytest.raises(ValueError, match="blocked"):
            validate_url("http://127.0.0.1:8080")
        with pytest.raises(ValueError, match="blocked"):
            validate_url("http://localhost:5000")

    def test_allow_private_ips(self):
        # Should not raise
        assert validate_url("http://localhost:5000", allow_private=True) == "http://localhost:5000"
        assert validate_url("http://192.168.1.1", allow_private=True) == "http://192.168.1.1"

@pytest.mark.asyncio
async def test_mcp_driver_lifecycle():
    driver = MCPDriver(headless=True)
    try:
        await driver.start()
        assert driver.browser.is_connected()
        assert driver.page is not None
        
        # Test basic navigation via driver
        await driver.page.goto("http://example.com")
        assert "example.com" in driver.page.url
        
        await driver.cleanup()
        assert driver.pw is None
    finally:
        if driver.pw:
            await driver.cleanup()

@pytest.mark.asyncio
async def test_mcp_driver_ssrf_interception():
    # This tests the request-level interception in the driver
    driver = MCPDriver(headless=True, allow_private=False)
    try:
        await driver.start()
        
        # We can't easily test the 'abort' directly without a full MCP server run,
        # but we can verify that navigation to a blocked URL fails.
        # Note: validate_url is called inside browser_navigate tool, 
        # but the interceptor handles resource-level SSRF.
        
        with pytest.raises(Exception):
            await driver.page.goto("http://127.0.0.1:9999")
            
    finally:
        await driver.cleanup()
