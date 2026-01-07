# Agent Browser - AI Agent Quick Reference

> **For AI agents only.** This file contains concise, functional information for automated browser control.

## First Steps (Start Here!)

At the start of any browser automation session:

```
1. get_agent_guide()      # Get this documentation via MCP (you're reading it now)
2. browser_status()       # Check capabilities, permissions, viewport
3. check_local_port(5000) # If testing local app, verify it's running
4. goto("http://...")     # Navigate to target
5. page_state()           # Get interactive elements with selectors
```

**Why this order?**
- `get_agent_guide()` gives you this documentation programmatically via MCP
- `browser_status()` tells you if localhost access is enabled (permissions)
- `check_local_port()` verifies the app is running BEFORE you try to navigate
- `page_state()` gives you ready-to-use selectors without needing a screenshot

**Note:** This documentation is available via `get_agent_guide()` tool. Call it with `section='selectors'|'tools'|'patterns'|'errors'` for specific sections.

## Capabilities Summary

```json
{
  "engine": "chromium",
  "selector_engines": ["css", "xpath", "text=", "id=", "placeholder=", ":has-text()", "nth="],
  "auto_wait": true,
  "default_timeout_ms": 10000,
  "localhost_support": "requires --allow-private flag",
  "mode": "mcp_server or cli"
}
```

## Selector Reference

All selectors use **Playwright's selector engine** - NOT standard `document.querySelector()`.

| Type | Syntax | Example |
|------|--------|---------|
| CSS | `selector` | `#login-btn`, `.nav-item`, `button` |
| Text (exact) | `text="..."` | `text="Sign In"` |
| Text (partial) | `text=...` | `text=Sign` |
| Has text | `button:has-text("Submit")` | Matches `<button>Submit Form</button>` |
| XPath | `xpath=...` | `xpath=//button[@type="submit"]` |
| Placeholder | `placeholder=...` | `placeholder=Enter email` |
| Nth match | `selector >> nth=N` | `.item >> nth=0` (first), `.item >> nth=-1` (last) |
| Chained | `parent >> child` | `#form >> button` |

**Important:** The `:has-text()` pseudo-selector works in `click`, `fill`, `wait_for` tools - NOT in `evaluate` (which uses raw browser JS).

## Wait Behavior

**All interaction tools auto-wait** for elements to be:
- Attached to DOM
- Visible
- Stable (not animating)
- Enabled (for inputs)

You do NOT need to call `wait_for` before `click` or `fill`. Only use explicit waits for:
- Dynamic content loading after actions
- Text that appears asynchronously
- URL changes after form submission

## Tool Categories

### Navigation (auto-waits for page load)
- `goto(url)` - Navigate (validates URL, blocks private IPs by default)
- `back()`, `forward()`, `reload()` - History navigation
- `get_url()` - Current URL

### Interactions (auto-wait for actionability)
- `click(selector)` - Click element
- `click_nth(selector, index)` - Click nth match (0-indexed)
- `fill(selector, value)` - Clear and fill input
- `type(selector, text)` - Type with key events (slower, triggers JS handlers)
- `select(selector, value)` - Select dropdown option
- `hover(selector)`, `focus(selector)` - Mouse/focus actions
- `press(key)` - Keyboard: "Enter", "Tab", "Escape", "ArrowDown"
- `upload(selector, file_path)` - Upload file to `<input type="file">` (absolute path required)

### Waiting (explicit waits)
- `wait(duration_ms)` - Hard wait (avoid when possible)
- `wait_for(selector)` - Wait for element to appear
- `wait_for_text(text)` - Wait for text anywhere on page
- `wait_for_url(pattern)` - Wait for URL to contain pattern
- `wait_for_load_state(state)` - "load", "domcontentloaded", "networkidle"

### Data Extraction
- `screenshot(name)` - Full-page PNG, returns file path
- `text(selector)` - Get text content
- `value(selector)` - Get input value
- `attr(selector, attribute)` - Get attribute value
- `count(selector)` - Count matching elements
- `evaluate(script)` - Run JavaScript, returns result

### Assertions (return PASS/FAIL, never throw)
- `assert_visible(selector)` - Check element visibility
- `assert_text(selector, expected)` - Check text contains expected
- `assert_url(pattern)` - Check URL contains pattern

### Page State
- `scroll(direction)` - "top", "bottom", "up", "down"
- `viewport(width, height)` - Resize viewport
- `cookies()` - Get all cookies
- `storage()` - Get localStorage as JSON
- `clear()` - Clear localStorage and sessionStorage

### Debugging
- `console()` - Get console log entries
- `network()` - Get network request log
- `dialog(action, prompt_text)` - Handle alert/confirm/prompt

### Agent Utilities
- `browser_status()` - **Call first!** Get capabilities, permissions, viewport, current page, and capability flags
- `check_local_port(port)` - Check if local service is running (localhost/127.0.0.1/::1 only, for security)
- `page_state()` - Get URL, title, and visible interactive elements with suggested selectors (masks sensitive fields)
- `find_elements(selector, include_hidden)` - Debug selectors, see all matching elements with details (masks sensitive fields)
- `suggest_next_actions()` - **NEW!** Context-aware hints based on page state (forms, errors, loading, modals)
- `validate_selector(selector)` - **NEW!** Validate selector before using - returns count, sample, suggestions

### Perception Tools (NEW - for reading page content)
- `get_page_markdown(selector?, max_length?)` - **Key for reading!** Extract page content as structured markdown (headings, lists, tables). Note: `selector` uses CSS only (#id, .class)
- `get_accessibility_tree(selector?, max_length?)` - Get accessibility tree as YAML-like text (roles, names, states)
- `find_relative(anchor, direction, target?)` - Find element spatially relative to anchor ('above', 'below', 'left', 'right', 'nearest'). Note: `anchor` uses Playwright selectors, `target` uses CSS only

### Advanced Tools
- `wait_for_change(selector, attribute?)` - Wait for element text/attribute to mutate (for SPAs)
- `highlight(selector, color?, duration_ms?)` - Visual debugging - draw border around element before screenshot
- `mock_network(url_pattern, response_body, status?, content_type?)` - Mock API calls for frontend testing
- `clear_mocks()` - Clear all network mocks

## Response Format

All tools return:
```json
{
  "success": true|false,
  "message": "Human-readable result or error",
  "data": { ... }  // Optional, for extraction tools
}
```

**Assertions** include `[PASS]` or `[FAIL]` prefix in message.

## Common Patterns

### Fill a form and submit
```
fill("#email", "user@example.com")
fill("#password", "secret123")
click("button[type='submit']")
wait_for_url("/dashboard")
```

### Click by visible text
```
click("text=Sign In")
click("button:has-text('Submit')")
```

### Wait for dynamic content
```
click("#load-more")
wait_for_text("Results loaded")
screenshot("after-load")
```

### Check form validation
```
click("#submit")
assert_visible(".error-message")
assert_text(".error-message", "Email is required")
```

### Handle nth element
```
click_nth(".product-card", 0)  // First product
click_nth(".product-card", -1) // Last product (not supported, use count first)
```

### Read calculation results (Perception)
```
get_page_markdown("#results-section")  // Get structured content
find_relative("text=Total Gain", "below", "span")  // Find value below label
```

### Debug and verify selectors
```
highlight("#submit-btn")  // Visual highlight before screenshot
screenshot("highlighted")  // Capture to verify
find_elements("button")  // See all matching buttons
```

### Wait for SPA updates
```
click("#calculate")
wait_for_change("#results", timeout_ms=5000)  // Wait for content change
get_page_markdown("#results")  // Read updated results
```

### Mock API for testing
```
mock_network("**/api/calculate*", '{"result": 12345}')
click("#calculate")  // Will use mocked response
clear_mocks()  // Restore normal behavior
```

### Validate before acting (prevent blind failures)
```
validate_selector("#submit-btn")  // Check if exists, get count
// Returns: {valid: true, count: 1, sample_tag: "button", sample_text: "Submit"}
click("#submit-btn")  // Now safe to click
```

### Get context-aware help when stuck
```
suggest_next_actions()  // Analyze page, get relevant tool suggestions
// Returns: suggestions for forms, errors, loading states, modals, etc.
```

## Tool Safety Levels

Use `get_agent_guide(section='safety')` for full details.

| Level | Tools | Retry Strategy |
|-------|-------|----------------|
| **SAFE** (read-only) | page_state, validate_selector, get_page_markdown, text, screenshot, assert_* | Retry freely |
| **MUTATING** | click, fill, type, upload, scroll, goto | Retry with caution |
| **EXTERNAL** | click buy/submit, fill payment forms | Confirm before retry |

## Capability Negotiation

`browser_status()` returns capability flags to branch logic:
```json
{
  "capabilities": {
    "javascript": true,
    "clipboard": false,  // Only in headed mode
    "file_download": true,
    "network_interception": true  // mock_network available
  }
}
```

## Localhost/Private IP Access

By default, private IPs (localhost, 127.0.0.1, 192.168.x.x, etc.) are **blocked**.

To test local apps, the server must be started with `--allow-private`:
```
agent-browser-mcp --allow-private
```

Check `browser_status()` to verify if private access is enabled.

## Security: Sensitive Field Masking

`page_state()` and `find_elements()` automatically mask values for sensitive fields to prevent credential leakage.

**Masked patterns** (in field name or id):
- `password`, `secret`, `token`, `key`, `credential`
- `ssn`, `cvv`, `pin`

**Example output:**
```json
{"id": "password", "type": "password", "value": "[MASKED]"}
{"id": "api_token", "type": "text", "value": "[MASKED]"}
{"id": "username", "type": "text", "value": "actual_value"}
```

## Error Handling

| Error Pattern | Likely Cause | Solution |
|---------------|--------------|----------|
| "Timeout exceeded" | Element not found or not actionable | Use `wait_for`, check selector |
| "strict mode violation" | Multiple elements match | Use more specific selector or `click_nth` |
| "Private IP targets are blocked" | Trying to access localhost | Need `--allow-private` flag |
| "element is not visible" | Hidden or off-screen | Scroll or check display state |

## Performance Tips

1. **Don't over-wait**: Tools auto-wait. Remove unnecessary `wait()` calls.
2. **Use `text=` selectors**: More resilient than CSS when IDs change.
3. **Batch reads**: Get multiple values in one turn when possible.
4. **Screenshot strategically**: Only when visual verification needed.

## File-Based State (CLI Mode Only)

In CLI mode, state is persisted to `.agent_browser/{session_id}/`:
- `state.json` - Current URL, session info
- `console.json` - Console log
- `network.json` - Network requests

You can read these directly instead of calling tools for state inspection.
