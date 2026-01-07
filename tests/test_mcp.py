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


# ============== AGENT UTILITY TOOLS TESTS ==============


@pytest.mark.asyncio
async def test_browser_status_before_navigation():
    """Test browser_status tool returns correct state before and after navigation."""
    server = BrowserServer("test-browser-status")
    server.configure(allow_private=True, headless=True)
    try:
        # Before any navigation, status should be idle
        result = await server.browser_status()
        assert result["success"] is True
        assert result["data"]["status"] == "idle"
        assert result["data"]["active_page"] is None
        assert "localhost" in result["data"]["permissions"]
        assert result["data"]["viewport"] == {"width": 1280, "height": 900}

        # After navigation, status should be ready
        await server.goto("http://example.com")
        result = await server.browser_status()
        assert result["success"] is True
        assert result["data"]["status"] == "ready"
        assert result["data"]["active_page"] is not None
        assert "example.com" in result["data"]["active_page"]["url"]

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_browser_status_viewport_tracking():
    """Test browser_status correctly reports viewport after resize."""
    server = BrowserServer("test-viewport-tracking")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        # Change viewport
        await server.viewport(800, 600)

        # Verify browser_status reports actual viewport
        result = await server.browser_status()
        assert result["success"] is True
        assert result["data"]["viewport"]["width"] == 800
        assert result["data"]["viewport"]["height"] == 600

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_check_local_port_ssrf_protection():
    """Test check_local_port blocks non-localhost hosts (SSRF protection)."""
    server = BrowserServer("test-port-ssrf")
    server.configure(allow_private=True, headless=True)

    # Should block metadata service
    result = await server.check_local_port(80, "169.254.169.254")
    assert result["success"] is False
    assert "not allowed" in result["message"]

    # Should block arbitrary hosts
    result = await server.check_local_port(80, "evil.com")
    assert result["success"] is False
    assert "not allowed" in result["message"]

    # Should allow localhost (not blocked for SSRF)
    result = await server.check_local_port(9999, "localhost")
    # Host is allowed - won't have "not allowed" in message
    # success may be True or False depending on port/OS, but not blocked
    assert "not allowed" not in result["message"]

    # Should allow 127.0.0.1
    result = await server.check_local_port(9999, "127.0.0.1")
    assert "not allowed" not in result["message"]

    # Should allow ::1 (IPv6 localhost)
    result = await server.check_local_port(9999, "::1")
    assert "not allowed" not in result["message"]


@pytest.mark.asyncio
async def test_page_state_returns_interactive_elements():
    """Test page_state returns interactive elements with selectors."""
    server = BrowserServer("test-page-state")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        # Create test page with various elements
        await server.evaluate("""
            document.body.innerHTML = `
                <h1>Test Page</h1>
                <input id="username" type="text" placeholder="Username">
                <input id="password" type="password" value="secret123">
                <input id="api_token" type="text" value="tok_abc123">
                <button id="submit">Submit</button>
                <a href="/link">Click here</a>
            `;
        """)

        result = await server.page_state()
        assert result["success"] is True
        assert result["data"]["url"] is not None
        assert result["data"]["element_count"] > 0

        # Check that password is masked
        elements = result["data"]["interactive_elements"]
        password_el = next((e for e in elements if e.get("id") == "password"), None)
        if password_el and password_el.get("value"):
            assert password_el["value"] == "[MASKED]"

        # Check that api_token is masked (contains "token")
        token_el = next((e for e in elements if e.get("id") == "api_token"), None)
        if token_el and token_el.get("value"):
            assert token_el["value"] == "[MASKED]"

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_find_elements_counts():
    """Test find_elements correctly counts visible and hidden elements."""
    server = BrowserServer("test-find-elements")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        # Create test page with visible and hidden elements
        await server.evaluate("""
            document.body.innerHTML = `
                <div class="item" style="display:block">Visible 1</div>
                <div class="item" style="display:block">Visible 2</div>
                <div class="item" style="display:none">Hidden 1</div>
                <div class="item" style="display:none">Hidden 2</div>
            `;
        """)

        # Without hidden elements
        result = await server.find_elements(".item", include_hidden=False)
        assert result["success"] is True
        assert result["data"]["visible_count"] == 2
        assert result["data"]["hidden_count"] == 2
        assert result["data"]["total_count"] == 4
        assert len(result["data"]["elements"]) == 2  # Only visible returned

        # With hidden elements
        result = await server.find_elements(".item", include_hidden=True)
        assert result["success"] is True
        assert result["data"]["total_count"] == 4
        assert len(result["data"]["elements"]) == 4  # All returned

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_find_elements_password_masking():
    """Test find_elements masks sensitive field values."""
    server = BrowserServer("test-find-elements-mask")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        await server.evaluate("""
            document.body.innerHTML = `
                <input id="user" type="text" value="john">
                <input id="pass" type="password" value="secret">
                <input id="api_key" type="text" value="key_123">
                <input id="ssn_field" type="text" value="123-45-6789">
            `;
        """)

        result = await server.find_elements("input")
        assert result["success"] is True

        elements = {e["id"]: e for e in result["data"]["elements"] if e.get("id")}

        # Regular field should show value
        assert elements["user"].get("value") == "john"

        # Password type should be masked
        assert elements["pass"].get("value") == "[MASKED]"

        # api_key (contains "key") should be masked
        assert elements["api_key"].get("value") == "[MASKED]"

        # ssn_field (contains "ssn") should be masked
        assert elements["ssn_field"].get("value") == "[MASKED]"

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_selector_hinting_on_click_failure():
    """Test that click failures return helpful selector suggestions."""
    server = BrowserServer("test-selector-hints")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        await server.evaluate("""
            document.body.innerHTML = `
                <button id="submit-btn">Submit Form</button>
                <button id="cancel-btn">Cancel</button>
                <a href="/login">Login</a>
            `;
        """)

        # Try to click non-existent element
        result = await server.click("#nonexistent-button")
        assert result["success"] is False

        # Should have suggestions
        if "suggestions" in result:
            assert len(result["suggestions"]) > 0
            # Suggestions should include actual page elements
            selectors = [s["selector"] for s in result["suggestions"]]
            assert any("submit" in s.lower() or "cancel" in s.lower() or "login" in s.lower() for s in selectors)

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_get_agent_guide():
    """Test get_agent_guide tool returns documentation for AI agents."""
    server = BrowserServer("test-agent-guide")
    server.configure(allow_private=True, headless=True)

    # Test full guide
    result = await server.get_agent_guide()
    assert result["success"] is True
    assert "content" in result["data"]
    assert "sections_available" in result["data"]
    assert "First Steps" in result["data"]["content"]
    assert "Selector Reference" in result["data"]["content"]

    # Test specific section
    result = await server.get_agent_guide(section="selectors")
    assert result["success"] is True
    assert "Selector Reference" in result["data"]["content"]
    assert "text=" in result["data"]["content"]

    # Test invalid section falls back gracefully
    result = await server.get_agent_guide(section="nonexistent")
    assert result["success"] is True
    assert "content" in result["data"]  # Returns full guide


@pytest.mark.asyncio
async def test_get_page_markdown():
    """Test get_page_markdown extracts structured content."""
    server = BrowserServer("test-markdown")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        await server.evaluate("""
            document.body.innerHTML = `
                <h1>Calculator Results</h1>
                <h2>Summary</h2>
                <ul>
                    <li>Total Invested: $10,000</li>
                    <li>Final Value: $15,000</li>
                </ul>
                <p>Your investment grew by 50%.</p>
            `;
        """)

        result = await server.get_page_markdown()
        assert result["success"] is True
        assert "Calculator Results" in result["data"]["content"]
        assert "Total Invested" in result["data"]["content"]
        assert result["data"]["lineCount"] > 0

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_find_relative():
    """Test find_relative locates elements spatially."""
    server = BrowserServer("test-find-relative")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        await server.evaluate("""
            document.body.innerHTML = `
                <div style="position:absolute; top:100px; left:100px;">
                    <span id="label">Total:</span>
                </div>
                <div style="position:absolute; top:130px; left:100px;">
                    <span id="value">$1,234</span>
                </div>
            `;
        """)

        # Find element below the label
        result = await server.find_relative("#label", "below")
        assert result["success"] is True
        assert result["data"]["found"] is True
        assert "$1,234" in result["data"]["element"]["text"]

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_highlight():
    """Test highlight adds visual border to elements."""
    server = BrowserServer("test-highlight")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        await server.evaluate("""
            document.body.innerHTML = '<button id="btn">Click Me</button>';
        """)

        result = await server.highlight("#btn", color="blue", duration_ms=100)
        assert result["success"] is True
        assert result["data"]["count"] == 1
        assert result["data"]["color"] == "blue"

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_assert_text_truncation():
    """Test assert_text truncates long content on failure."""
    server = BrowserServer("test-assert-truncation")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        # Create element with very long text
        await server.evaluate("""
            document.body.innerHTML = '<div id="content">' + 'x'.repeat(2000) + '</div>';
        """)

        # Search for text that doesn't exist
        result = await server.assert_text("#content", "NOT_FOUND_TEXT")
        assert result["success"] is True
        assert result["data"]["found"] is False
        # Check that content is truncated (not full 2000 chars)
        assert len(result["data"]["text"]) <= 510  # 500 + "..."
        assert result["data"]["total_length"] == 2000

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_mock_network():
    """Test mock_network intercepts and mocks API calls."""
    server = BrowserServer("test-mock-network")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        # Set up mock
        result = await server.mock_network(
            "**/api/test*",
            '{"mocked": true}',
            status=200,
        )
        assert result["success"] is True
        assert result["data"]["pattern"] == "**/api/test*"

        # Clear mocks
        result = await server.clear_mocks()
        assert result["success"] is True
        assert result["data"]["cleared_count"] == 1

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_validate_selector():
    """Test validate_selector checks selector validity and returns match info."""
    server = BrowserServer("test-validate-selector")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        # Create test elements
        await server.evaluate("""
            document.body.innerHTML = `
                <button id="single-btn">Click Me</button>
                <div class="item">Item 1</div>
                <div class="item">Item 2</div>
                <div class="item">Item 3</div>
            `;
        """)

        # Test valid selector with single match
        result = await server.validate_selector("#single-btn")
        assert result["success"] is True
        assert result["data"]["valid"] is True
        assert result["data"]["count"] == 1
        assert result["data"]["sample_tag"] == "button"
        assert "Click Me" in result["data"]["sample_text"]

        # Test selector with multiple matches
        result = await server.validate_selector(".item")
        assert result["success"] is True
        assert result["data"]["valid"] is True
        assert result["data"]["count"] == 3
        assert "note" in result["data"]  # Should have warning about multiple matches
        assert "suggested_selectors" in result["data"]

        # Test non-existent selector
        result = await server.validate_selector("#does-not-exist")
        assert result["success"] is True
        assert result["data"]["valid"] is False
        assert result["data"]["count"] == 0
        assert "suggestions" in result["data"]

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_suggest_next_actions():
    """Test suggest_next_actions provides context-aware hints."""
    server = BrowserServer("test-suggest-actions")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        # Create page with form
        await server.evaluate("""
            document.body.innerHTML = `
                <form>
                    <input type="text" id="name" placeholder="Name">
                    <input type="email" id="email" placeholder="Email">
                    <button type="submit">Submit</button>
                </form>
            `;
        """)

        result = await server.suggest_next_actions()
        assert result["success"] is True
        assert "suggestions" in result["data"]
        assert "page_context" in result["data"]
        assert result["data"]["page_context"]["has_form"] is True

        # Check that form-related suggestion is present
        suggestions = result["data"]["suggestions"]
        assert len(suggestions) > 0

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_browser_status_capabilities():
    """Test browser_status returns capability flags."""
    server = BrowserServer("test-capabilities")
    server.configure(allow_private=True, headless=True)
    try:
        await server.goto("http://example.com")

        result = await server.browser_status()
        assert result["success"] is True
        assert "capabilities" in result["data"]

        caps = result["data"]["capabilities"]
        assert caps["javascript"] is True
        assert caps["cookies"] is True
        assert caps["network_interception"] is True
        assert caps["screenshots"] is True
        # Headless mode affects these
        assert "clipboard" in caps
        assert "file_download" in caps

    finally:
        await server.stop()
