"""Tests for MCP server functionality."""

import pytest
from agent_browser.mcp import URLValidator, BrowserServer


# Fixtures are defined in conftest.py:
# - shared_browser: Module-scoped browser instance for all tests
# - fresh_page: Fresh page state for each test (navigates to example.com)


def validate_url(url: str, allow_private: bool = False) -> str:
    """Convenience wrapper for testing that returns URL if valid."""
    URLValidator.is_safe_url(url, allow_private=allow_private)
    return url


# =============================================================================
# Non-Browser Tests (Fast - no browser needed)
# Run with: pytest -m no_browser
# =============================================================================


@pytest.mark.no_browser
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


@pytest.mark.no_browser
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


# =============================================================================
# Browser Tests (Using Shared Fixture)
# =============================================================================


@pytest.mark.asyncio
async def test_browser_server_lifecycle():
    """Test browser start/stop lifecycle - uses its own server."""
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
async def test_browser_server_ssrf_protection(shared_browser):
    """Test SSRF protection blocks private IPs."""
    # Save original setting
    original_allow_private = shared_browser.allow_private
    shared_browser.allow_private = False

    try:
        # Navigation to private IPs should fail via validation
        result = await shared_browser.goto("http://127.0.0.1:9999")
        assert result["success"] is False
        assert "blocked" in result["message"].lower() or "private" in result["message"].lower()
    finally:
        shared_browser.allow_private = original_allow_private


@pytest.mark.asyncio
async def test_browser_server_tools(fresh_page):
    """Test basic browser tools."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_new_mcp_tools(fresh_page):
    """Test the 13 new MCP tools added in v0.1.6."""
    server = fresh_page

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

    # Test clear (storage) - Note: data URLs don't have localStorage access,
    # so this will fail on data: URLs. We test that it doesn't crash.
    result = await server.clear()
    # On data: URLs, this fails because they have no origin for storage
    # On real URLs (http/https), this would succeed
    assert "success" in result

    # Test dialog (set handler)
    result = await server.dialog("accept")
    assert result["success"] is True

    # Test reload (last since it clears the page)
    result = await server.reload()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_select_tool(fresh_page):
    """Test the select dropdown tool."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_url_and_load_state_tools(fresh_page):
    """Test the 3 new URL/navigation tools added for app testing."""
    server = fresh_page

    # Test assert_url (positive) - we're on a data: URL
    result = await server.assert_url("data:")
    assert result["success"] is True
    assert result["data"]["match"] is True
    assert "[PASS]" in result["message"]

    # Test assert_url (negative)
    result = await server.assert_url("notfound.xyz")
    assert result["success"] is True
    assert result["data"]["match"] is False
    assert "[FAIL]" in result["message"]

    # Test wait_for_url (already on the URL)
    result = await server.wait_for_url("data:", timeout_ms=1000)
    assert result["success"] is True
    assert "data:" in result["data"]["url"]

    # Test wait_for_load_state
    result = await server.wait_for_load_state("domcontentloaded")
    assert result["success"] is True

    result = await server.wait_for_load_state("networkidle")
    assert result["success"] is True

    # Test invalid state
    result = await server.wait_for_load_state("invalid_state")
    assert result["success"] is False
    assert "Invalid state" in result["message"]


# ============== AGENT UTILITY TOOLS TESTS ==============


@pytest.mark.asyncio
async def test_browser_status_before_navigation():
    """Test browser_status tool returns correct state before and after navigation.

    Note: This test uses its own server to test idle state before navigation.
    """
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
async def test_browser_status_viewport_tracking(fresh_page):
    """Test browser_status correctly reports viewport after resize."""
    server = fresh_page

    # Change viewport
    await server.viewport(800, 600)

    # Verify browser_status reports actual viewport
    result = await server.browser_status()
    assert result["success"] is True
    assert result["data"]["viewport"]["width"] == 800
    assert result["data"]["viewport"]["height"] == 600


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_check_local_port_ssrf_protection():
    """Test check_local_port blocks non-localhost hosts (SSRF protection).

    Note: This test doesn't need a running browser - uses its own server instance.
    """
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
async def test_page_state_returns_interactive_elements(fresh_page):
    """Test page_state returns interactive elements with selectors."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_find_elements_counts(fresh_page):
    """Test find_elements correctly counts visible and hidden elements."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_find_elements_password_masking(fresh_page):
    """Test find_elements masks sensitive field values."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_selector_hinting_on_click_failure(fresh_page):
    """Test that click failures return helpful selector suggestions."""
    server = fresh_page

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


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_get_agent_guide():
    """Test get_agent_guide tool returns documentation for AI agents.

    Note: Doesn't need browser - just returns static documentation.
    """
    server = BrowserServer("test-agent-guide")

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
async def test_get_page_markdown(fresh_page):
    """Test get_page_markdown extracts structured content."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_find_relative(fresh_page):
    """Test find_relative locates elements spatially."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_highlight(fresh_page):
    """Test highlight adds visual border to elements."""
    server = fresh_page

    await server.evaluate("""
        document.body.innerHTML = '<button id="btn">Click Me</button>';
    """)

    result = await server.highlight("#btn", color="blue", duration_ms=100)
    assert result["success"] is True
    assert result["data"]["count"] == 1
    assert result["data"]["color"] == "blue"


@pytest.mark.asyncio
async def test_assert_text_truncation(fresh_page):
    """Test assert_text truncates long content on failure."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_mock_network(fresh_page):
    """Test mock_network intercepts and mocks API calls."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_validate_selector(fresh_page):
    """Test validate_selector checks selector validity and returns match info."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_suggest_next_actions(fresh_page):
    """Test suggest_next_actions provides context-aware hints."""
    server = fresh_page

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


@pytest.mark.asyncio
async def test_browser_status_capabilities(fresh_page):
    """Test browser_status returns capability flags."""
    server = fresh_page

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


# =============================================================================
# Cinematic Engine - Phase 1: Voice & Timing Tests (No browser needed)
# =============================================================================


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_generate_voiceover_tool_exists():
    """Test that generate_voiceover tool is registered and callable."""
    server = BrowserServer("test-cinematic")
    tool_names = [t.name for t in server.server._tool_manager.list_tools()]
    assert "generate_voiceover" in tool_names


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_generate_voiceover_invalid_provider():
    """Test generate_voiceover returns error for unknown provider."""
    server = BrowserServer("test-cinematic")
    result = await server.generate_voiceover(
        text="Test text",
        provider="unknown_provider"
    )
    assert result["success"] is False
    assert "Unknown TTS provider" in result["message"]


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_get_audio_duration_tool_exists():
    """Test that get_audio_duration tool is registered and callable."""
    server = BrowserServer("test-cinematic")
    tool_names = [t.name for t in server.server._tool_manager.list_tools()]
    assert "get_audio_duration" in tool_names


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_get_audio_duration_nonexistent_file():
    """Test get_audio_duration handles missing files gracefully."""
    server = BrowserServer("test-cinematic")
    result = await server.get_audio_duration("/nonexistent/path/audio.mp3")
    assert result["success"] is False
    # Either mutagen not installed or file not found
    assert "not installed" in result["message"] or "Could not read" in result["message"] or "Failed" in result["message"]


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_cinematic_engine_state_initialized():
    """Test that Cinematic Engine state variables are properly initialized."""
    server = BrowserServer("test-cinematic")

    # Check TTS state variables exist
    assert server._tts_client is None  # Lazy-loaded
    assert server._audio_cache_dir.name == "audio_cache"

    # Check recording state variables (Phase 2)
    assert server._recording is False
    assert server._video_dir.name == "videos"
    assert server._cursor_injected is False


# =============================================================================
# Cinematic Engine - Phase 2: Recording & Virtual Actor Tests (No browser needed)
# =============================================================================


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_recording_tools_exist():
    """Test that Phase 2 recording tools are registered."""
    server = BrowserServer("test-recording")
    tool_names = [t.name for t in server.server._tool_manager.list_tools()]

    assert "start_recording" in tool_names
    assert "stop_recording" in tool_names
    assert "recording_status" in tool_names
    assert "annotate" in tool_names
    assert "clear_annotations" in tool_names


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_recording_status_initial():
    """Test recording_status returns not recording initially."""
    server = BrowserServer("test-recording")
    result = await server.recording_status()

    assert result["success"] is True
    assert result["data"]["recording"] is False
    assert result["data"]["cursor_injected"] is False


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_stop_recording_when_not_recording():
    """Test stop_recording returns error when not recording."""
    server = BrowserServer("test-recording")
    result = await server.stop_recording()

    assert result["success"] is False
    assert "Not currently recording" in result["message"]


@pytest.mark.asyncio
async def test_start_recording_twice_fails():
    """Test that starting recording twice fails.

    Note: This test needs its own server to test recording state.
    """
    server = BrowserServer("test-recording")
    server.configure(allow_private=True, headless=True)

    try:
        # Start first recording
        result1 = await server.start_recording()
        assert result1["success"] is True

        # Try to start second recording
        result2 = await server.start_recording()
        assert result2["success"] is False
        assert "Already recording" in result2["message"]

    finally:
        await server.stop()


# =============================================================================
# Cinematic Engine - Phase 3: Camera Control Tests
# =============================================================================


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_camera_tools_exist():
    """Test that Phase 3 camera tools are registered."""
    server = BrowserServer("test-camera")
    tool_names = [t.name for t in server.server._tool_manager.list_tools()]

    assert "camera_zoom" in tool_names
    assert "camera_pan" in tool_names
    assert "camera_reset" in tool_names


@pytest.mark.asyncio
async def test_camera_zoom_element_not_found(fresh_page):
    """Test camera_zoom returns error for non-existent selector."""
    server = fresh_page

    result = await server.camera_zoom(
        selector="#nonexistent-element",
        level=1.5,
        duration_ms=100
    )
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@pytest.mark.asyncio
async def test_camera_zoom_success(fresh_page):
    """Test camera_zoom works on valid selector."""
    server = fresh_page

    result = await server.camera_zoom(
        selector="h1",
        level=1.5,
        duration_ms=100
    )
    assert result["success"] is True
    assert result["data"]["level"] == 1.5
    assert result["data"]["target"] == "h1"


@pytest.mark.asyncio
async def test_camera_pan_element_not_found(fresh_page):
    """Test camera_pan returns error for non-existent selector."""
    server = fresh_page

    result = await server.camera_pan(
        selector="#nonexistent-element",
        duration_ms=100
    )
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@pytest.mark.asyncio
async def test_camera_pan_success(fresh_page):
    """Test camera_pan works on valid selector."""
    server = fresh_page

    result = await server.camera_pan(
        selector="p",
        duration_ms=100
    )
    assert result["success"] is True
    assert result["data"]["target"] == "p"


@pytest.mark.asyncio
async def test_camera_reset(fresh_page):
    """Test camera_reset succeeds."""
    server = fresh_page

    # First zoom in
    await server.camera_zoom(selector="h1", level=2.0, duration_ms=100)

    # Then reset
    result = await server.camera_reset(duration_ms=100)
    assert result["success"] is True
    assert "reset" in result["message"].lower()


# =============================================================================
# Cinematic Engine - Phase 4: Post-Production Tests (No browser needed)
# =============================================================================


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_postproduction_tools_exist():
    """Test that Phase 4 post-production tools are registered."""
    server = BrowserServer("test-postprod")
    tool_names = [t.name for t in server.server._tool_manager.list_tools()]

    assert "check_environment" in tool_names
    assert "merge_audio_video" in tool_names
    assert "add_background_music" in tool_names
    assert "get_video_duration" in tool_names


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_check_environment():
    """Test check_environment returns environment status."""
    server = BrowserServer("test-postprod")
    result = await server.check_environment()

    assert "success" in result
    assert "data" in result
    assert "ffmpeg" in result["data"]
    assert "openai_key" in result["data"]
    assert "elevenlabs_key" in result["data"]
    assert "errors" in result["data"]
    assert "warnings" in result["data"]


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_merge_audio_video_missing_video():
    """Test merge_audio_video handles missing video file."""
    server = BrowserServer("test-postprod")
    result = await server.merge_audio_video(
        video="/nonexistent/video.webm",
        audio_tracks=[{"path": "/some/audio.mp3", "start_ms": 0}],
        output="/output.mp4",
    )

    assert result["success"] is False
    assert "not found" in result["message"].lower()


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_merge_audio_video_no_tracks():
    """Test merge_audio_video handles empty audio tracks."""
    import tempfile
    import os

    # Create a temporary "video" file so we get past the video check
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(b"fake video content")
        video_path = f.name

    try:
        server = BrowserServer("test-postprod")
        result = await server.merge_audio_video(
            video=video_path,
            audio_tracks=[],
            output="/output.mp4",
        )

        assert result["success"] is False
        assert "no audio" in result["message"].lower()
    finally:
        os.unlink(video_path)


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_add_background_music_missing_video():
    """Test add_background_music handles missing video file."""
    server = BrowserServer("test-postprod")
    result = await server.add_background_music(
        video="/nonexistent/video.mp4",
        music="/some/music.mp3",
        output="/output.mp4",
    )

    assert result["success"] is False
    assert "not found" in result["message"].lower()


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_add_background_music_missing_music():
    """Test add_background_music handles missing music file."""
    import tempfile
    import os

    # Create a temporary "video" file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"fake video content")
        video_path = f.name

    try:
        server = BrowserServer("test-postprod")
        result = await server.add_background_music(
            video=video_path,
            music="/nonexistent/music.mp3",
            output="/output.mp4",
        )

        assert result["success"] is False
        assert "not found" in result["message"].lower()
    finally:
        os.unlink(video_path)


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_get_video_duration_missing_file():
    """Test get_video_duration handles missing file."""
    server = BrowserServer("test-postprod")
    result = await server.get_video_duration("/nonexistent/video.mp4")

    assert result["success"] is False
    assert "not found" in result["message"].lower()


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_stock_music_tools_exist():
    """Test that stock music tools are registered."""
    server = BrowserServer("test-stock-music")
    tool_names = [t.name for t in server.server._tool_manager.list_tools()]

    assert "list_stock_music" in tool_names
    assert "download_stock_music" in tool_names


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_list_stock_music_no_api_key(monkeypatch):
    """Test list_stock_music handles missing API key."""
    # Ensure JAMENDO_CLIENT_ID is not set
    monkeypatch.delenv("JAMENDO_CLIENT_ID", raising=False)

    server = BrowserServer("test-stock-music")
    result = await server.list_stock_music(query="background")

    assert result["success"] is False
    assert "JAMENDO_CLIENT_ID" in result["message"]


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_list_stock_music_with_mock(monkeypatch):
    """Test list_stock_music correctly parses Jamendo API response."""
    import aiohttp
    from unittest.mock import AsyncMock, MagicMock

    # Set a fake client ID
    monkeypatch.setenv("JAMENDO_CLIENT_ID", "test_client_id")

    # Mock response data matching Jamendo API format
    mock_response_data = {
        "headers": {
            "status": "success",
            "code": 0,
            "results_count": 2,
            "results_fullcount": 150,
        },
        "results": [
            {
                "id": "1532771",
                "name": "Corporate Vibes",
                "duration": 120,
                "artist_name": "Test Artist",
                "album_name": "Test Album",
                "audio": "https://example.com/stream.mp3",
                "audiodownload": "https://example.com/download.mp3",
                "album_image": "https://example.com/cover.jpg",
                "shareurl": "https://jamendo.com/track/123",
                "license_ccurl": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
            },
            {
                "id": "1532772",
                "name": "Epic Trailer",
                "duration": 180,
                "artist_name": "Another Artist",
                "album_name": "",
                "audio": "https://example.com/stream2.mp3",
                "audiodownload": "https://example.com/download2.mp3",
            },
        ],
    }

    # Create mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)

    # Create mock session
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Patch aiohttp.ClientSession
    monkeypatch.setattr(aiohttp, "ClientSession", lambda: mock_session)

    server = BrowserServer("test-stock-music")
    result = await server.list_stock_music(query="corporate", tags="pop")

    assert result["success"] is True
    assert result["data"]["total"] == 150
    assert len(result["data"]["tracks"]) == 2

    # Verify first track parsing
    track1 = result["data"]["tracks"][0]
    assert track1["id"] == "1532771"
    assert track1["name"] == "Corporate Vibes"
    assert track1["duration_sec"] == 120
    assert track1["artist"] == "Test Artist"
    assert track1["download_url"] == "https://example.com/download.mp3"
    assert track1["license"] == "CC BY-NC-SA"

    # Verify second track (with missing fields)
    track2 = result["data"]["tracks"][1]
    assert track2["id"] == "1532772"
    assert track2["album"] == ""  # Missing album handled


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_list_stock_music_empty_results(monkeypatch):
    """Test list_stock_music handles empty results gracefully."""
    import aiohttp
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setenv("JAMENDO_CLIENT_ID", "test_client_id")

    mock_response_data = {
        "headers": {"status": "success", "results_count": 0, "results_fullcount": 0},
        "results": [],
    }

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(aiohttp, "ClientSession", lambda: mock_session)

    server = BrowserServer("test-stock-music")
    result = await server.list_stock_music(query="nonexistent_query_xyz")

    assert result["success"] is True
    assert result["data"]["total"] == 0
    assert len(result["data"]["tracks"]) == 0
    assert "Found 0 tracks" in result["message"]


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_download_stock_music_invalid_url():
    """Test download_stock_music handles invalid URL."""
    server = BrowserServer("test-stock-music")
    result = await server.download_stock_music(url="not-a-valid-url")

    assert result["success"] is False
    assert "Invalid URL" in result["message"]


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_download_stock_music_nonexistent_url():
    """Test download_stock_music handles non-existent URL."""
    server = BrowserServer("test-stock-music")
    result = await server.download_stock_music(
        url="https://nonexistent.invalid/track.mp3"
    )

    assert result["success"] is False
    # Should fail due to connection error or 404


# =============================================================================
# Cinematic Engine - Phase 5: Polish Tests
# =============================================================================


@pytest.mark.no_browser
@pytest.mark.asyncio
async def test_polish_tools_exist():
    """Test that Phase 5 polish tools are registered."""
    server = BrowserServer("test-polish")
    tool_names = [t.name for t in server.server._tool_manager.list_tools()]

    assert "smooth_scroll" in tool_names
    assert "type_human" in tool_names
    assert "set_presentation_mode" in tool_names
    assert "freeze_time" in tool_names


@pytest.mark.asyncio
async def test_smooth_scroll_invalid_direction(fresh_page):
    """Test smooth_scroll handles invalid direction."""
    server = fresh_page

    result = await server.smooth_scroll(
        direction="sideways",
        duration_ms=100
    )
    assert result["success"] is False
    assert "invalid" in result["message"].lower()


@pytest.mark.asyncio
async def test_smooth_scroll_down(fresh_page):
    """Test smooth_scroll scrolls down."""
    server = fresh_page

    result = await server.smooth_scroll(
        direction="down",
        amount=200,
        duration_ms=100
    )
    assert result["success"] is True
    assert result["data"]["direction"] == "down"


@pytest.mark.asyncio
async def test_type_human_element_not_found(fresh_page):
    """Test type_human handles missing element."""
    server = fresh_page

    result = await server.type_human(
        selector="#nonexistent-input",
        text="Hello",
        wpm=120
    )
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@pytest.mark.asyncio
async def test_type_human_success(fresh_page):
    """Test type_human types text into input."""
    server = fresh_page

    # Create a test input
    await server.evaluate("""
        document.body.innerHTML = '<input type="text" id="test-input">';
    """)

    result = await server.type_human(
        selector="#test-input",
        text="Hi",
        wpm=300,  # Fast for testing
        variance=0.1
    )
    assert result["success"] is True
    assert result["data"]["wpm"] == 300


@pytest.mark.asyncio
async def test_set_presentation_mode(fresh_page):
    """Test set_presentation_mode enables/disables mode."""
    server = fresh_page

    # Enable
    result = await server.set_presentation_mode(enabled=True)
    assert result["success"] is True
    assert result["data"]["presentation_mode"] is True

    # Disable
    result = await server.set_presentation_mode(enabled=False)
    assert result["success"] is True
    assert result["data"]["presentation_mode"] is False


@pytest.mark.asyncio
async def test_freeze_time(fresh_page):
    """Test freeze_time freezes and restores time."""
    server = fresh_page

    # Freeze time
    result = await server.freeze_time(timestamp="2024-06-15T10:30:00")
    assert result["success"] is True
    assert result["data"]["frozen_at"] == "2024-06-15T10:30:00"

    # Restore time
    result = await server.freeze_time(timestamp=None)
    assert result["success"] is True
    assert result["data"]["frozen_at"] is None
