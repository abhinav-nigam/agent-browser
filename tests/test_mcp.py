"""Tests for MCP server functionality."""

import pytest
from agent_browser.mcp import URLValidator, BrowserServer


def validate_url(url: str, allow_private: bool = False) -> str:
    """Convenience wrapper for testing that returns URL if valid."""
    URLValidator.is_safe_url(url, allow_private=allow_private)
    return url


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

    def test_credentials_blocked(self):
        with pytest.raises(ValueError, match="credentials"):
            validate_url("http://user:pass@example.com")

    def test_invalid_hostname(self):
        with pytest.raises(ValueError, match="Invalid"):
            validate_url("http://")

    def test_unsupported_scheme(self):
        with pytest.raises(ValueError, match="Forbidden scheme"):
            validate_url("gopher://example.com")


class TestURLValidatorMethods:
    def test_is_private_ip_loopback(self):
        assert URLValidator.is_private_ip("127.0.0.1") is True
        assert URLValidator.is_private_ip("127.0.0.5") is True

    def test_is_private_ip_private_ranges(self):
        assert URLValidator.is_private_ip("10.0.0.1") is True
        assert URLValidator.is_private_ip("172.16.0.1") is True
        assert URLValidator.is_private_ip("192.168.1.1") is True

    def test_is_private_ip_public(self):
        assert URLValidator.is_private_ip("8.8.8.8") is False
        assert URLValidator.is_private_ip("142.250.80.46") is False

    def test_is_private_ip_invalid(self):
        assert URLValidator.is_private_ip("not-an-ip") is False
        assert URLValidator.is_private_ip("example.com") is False


@pytest.mark.asyncio
async def test_browser_server_lifecycle():
    server = BrowserServer("test-server")
    try:
        await server.start(headless=True)
        assert server.browser is not None
        assert server.browser.is_connected()
        assert server.page is not None

        # Navigate to example.com (public URL)
        server.allow_private = False
        result = await server.goto("http://example.com")
        assert result["success"] is True
        assert "example.com" in server.page.url

        await server.stop()
        assert server.playwright is None
        assert server.browser is None
    finally:
        if server.playwright:
            await server.stop()


@pytest.mark.asyncio
async def test_browser_server_ssrf_protection():
    server = BrowserServer("test-ssrf")
    server.allow_private = False
    try:
        await server.start(headless=True)

        # Navigation to private IPs should fail via validation
        result = await server.goto("http://127.0.0.1:9999")
        assert result["success"] is False
        assert "blocked" in result["message"].lower() or "private" in result["message"].lower()

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_browser_server_tools():
    server = BrowserServer("test-tools")
    server.allow_private = True  # Allow localhost for testing
    try:
        await server.start(headless=True)

        # Test get_url
        url_result = await server.get_url()
        assert url_result["success"] is True
        assert "url" in url_result["data"]

        # Test evaluate
        eval_result = await server.evaluate("1 + 1")
        assert eval_result["success"] is True
        assert eval_result["data"]["result"] == 2

        # Test scroll
        scroll_result = await server.scroll("down")
        assert scroll_result["success"] is True

        # Test wait
        wait_result = await server.wait(100)
        assert wait_result["success"] is True

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_new_mcp_tools():
    """Test the 13 new MCP tools added in v0.1.6."""
    server = BrowserServer("test-new-tools")
    server.allow_private = True
    try:
        await server.start(headless=True)

        # Navigate to a real page first (needed for localStorage access)
        await server.goto("http://example.com")

        # Create a test page with elements
        await server.evaluate("""
            document.body.innerHTML = `
                <h1 id="title">Test Page</h1>
                <input id="text-input" type="text" value="initial value">
                <a id="link" href="https://example.com">Click me</a>
                <select id="dropdown">
                    <option value="a">Option A</option>
                    <option value="b">Option B</option>
                </select>
                <div id="hidden" style="display:none">Hidden content</div>
                <div id="visible">Visible content</div>
                <button id="btn">Submit</button>
            `;
        """)

        # Small wait for DOM to stabilize (helps on slower CI machines)
        await server.wait(100)

        # Test wait_for (element already exists)
        result = await server.wait_for("#title", timeout_ms=2000)
        assert result["success"] is True

        # Test wait_for_text
        result = await server.wait_for_text("Test Page", timeout_ms=1000)
        assert result["success"] is True

        # Test text
        result = await server.text("#title")
        assert result["success"] is True
        assert result["data"]["text"] == "Test Page"

        # Test value
        result = await server.value("#text-input")
        assert result["success"] is True
        assert result["data"]["value"] == "initial value"

        # Test attr
        result = await server.attr("#link", "href")
        assert result["success"] is True
        assert result["data"]["value"] == "https://example.com"

        # Test count
        result = await server.count("div")
        assert result["success"] is True
        assert result["data"]["count"] >= 2

        # Test press
        result = await server.press("Tab")
        assert result["success"] is True

        # Test viewport
        result = await server.viewport(1024, 768)
        assert result["success"] is True
        assert "1024x768" in result["message"]

        # Test assert_visible
        result = await server.assert_visible("#visible")
        assert result["success"] is True
        assert result["data"]["visible"] is True
        assert "[PASS]" in result["message"]

        # Test assert_visible (negative case)
        result = await server.assert_visible("#hidden")
        assert result["success"] is True
        assert result["data"]["visible"] is False
        assert "[FAIL]" in result["message"]

        # Test assert_text
        result = await server.assert_text("#title", "Test")
        assert result["success"] is True
        assert result["data"]["found"] is True
        assert "[PASS]" in result["message"]

        # Test assert_text (negative case)
        result = await server.assert_text("#title", "Not Found")
        assert result["success"] is True
        assert result["data"]["found"] is False
        assert "[FAIL]" in result["message"]

        # Test clear (storage) - must be before reload since about:blank has no localStorage
        result = await server.clear()
        assert result["success"] is True

        # Test dialog (set handler)
        result = await server.dialog("accept")
        assert result["success"] is True

        # Test reload (last since it clears the page)
        result = await server.reload()
        assert result["success"] is True

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_select_tool():
    """Test the select dropdown tool."""
    server = BrowserServer("test-select")
    server.allow_private = True
    try:
        await server.start(headless=True)

        # Create a test page with a select
        await server.evaluate("""
            document.body.innerHTML = `
                <select id="country">
                    <option value="">Select...</option>
                    <option value="us">United States</option>
                    <option value="uk">United Kingdom</option>
                    <option value="in">India</option>
                </select>
            `;
        """)

        # Test select
        result = await server.select("#country", "uk")
        assert result["success"] is True

        # Verify selection
        result = await server.value("#country")
        assert result["success"] is True
        assert result["data"]["value"] == "uk"

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_url_and_load_state_tools():
    """Test the 3 new URL/navigation tools added for app testing."""
    server = BrowserServer("test-url-tools")
    server.allow_private = True
    try:
        await server.start(headless=True)

        # Navigate to example.com
        await server.goto("http://example.com")

        # Test assert_url (positive)
        result = await server.assert_url("example.com")
        assert result["success"] is True
        assert result["data"]["match"] is True
        assert "[PASS]" in result["message"]

        # Test assert_url (negative)
        result = await server.assert_url("notfound.xyz")
        assert result["success"] is True
        assert result["data"]["match"] is False
        assert "[FAIL]" in result["message"]

        # Test wait_for_url (already on the URL)
        result = await server.wait_for_url("example", timeout_ms=1000)
        assert result["success"] is True
        assert "example" in result["data"]["url"]

        # Test wait_for_load_state
        result = await server.wait_for_load_state("domcontentloaded")
        assert result["success"] is True

        result = await server.wait_for_load_state("networkidle")
        assert result["success"] is True

        # Test invalid state
        result = await server.wait_for_load_state("invalid_state")
        assert result["success"] is False
        assert "Invalid state" in result["message"]

    finally:
        await server.stop()
