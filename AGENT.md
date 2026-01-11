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
- Use `page_state(include_text=True)` to also get page headings and key text content

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
- `page_state(include_text?)` - Get URL, title, and visible interactive elements with suggested selectors. Set `include_text=True` for headings + key text summary (masks sensitive fields)
- `find_elements(selector, include_hidden)` - Debug selectors, see all matching elements with details (masks sensitive fields)
- `suggest_next_actions()` - **NEW!** Context-aware hints based on page state (forms, errors, loading, modals)
- `validate_selector(selector)` - **NEW!** Validate selector before using - returns count, sample, suggestions

### Perception Tools (NEW - for reading page content)
- `get_page_markdown(selector?, max_length?)` - **Key for reading!** Extract page content as structured markdown (headings, lists, tables). Note: `selector` uses CSS only (#id, .class)
- `get_accessibility_tree(selector?, max_length?)` - Get accessibility tree as YAML-like text (roles, names, states)
- `find_relative(anchor, direction, target?)` - Find element spatially relative to anchor ('above', 'below', 'left', 'right', 'nearest'). `target` can be CSS selector OR `"text"` to find nearest text content (recommended for reading values)

### Advanced Tools
- `wait_for_change(selector, attribute?)` - Wait for element text/attribute to mutate (for SPAs)
- `highlight(selector, color?, duration_ms?)` - Visual debugging - draw border around element before screenshot
- `mock_network(url_pattern, response_body, status?, content_type?)` - Mock API calls for frontend testing
- `clear_mocks()` - Clear all network mocks

### Cinematic Engine - Video Production (requires `pip install ai-agent-browser[video]`)

**Phase 1: Voice & Timing**
- `generate_voiceover(text, provider?, voice?, speed?, stability?, similarity_boost?, style?, use_speaker_boost?)` - Generate TTS audio using OpenAI or ElevenLabs. Cached to avoid redundant API calls.
  - ElevenLabs voice modulation for natural speech:
    - `stability` (0.0-1.0): Lower = more expressive. Try 0.3-0.4 for natural speech
    - `similarity_boost` (0.0-1.0): Voice clarity. Try 0.5-0.7 for natural speech
    - `style` (0.0-1.0): Expressiveness. Try 0.2-0.4 for engaging narration
  - Recommended voices: `H2JKG8QcEaH9iUMauArc` (Abhinav), `qr9D67rNgxf5xNgv46nx` (Tarun)
- `get_audio_duration(path)` - Get audio file duration in ms/sec for timing video actions

**Phase 2: Recording & Virtual Actor**
- `start_recording(filename?, width?, height?)` - Start video recording with virtual cursor (recreates context)
- `stop_recording()` - Stop recording and return video path (WebM format)
- `recording_status()` - Check if recording, get duration
- `annotate(text, target?, position?, style?, duration_ms?)` - Add floating text label (for callouts). Positions: above, below, left, right, top-right, bottom-left, center
- `clear_annotations()` - Remove all annotations
- `spotlight(selector, style?, color?, pulse_ms?, dim_opacity?)` - Cinematic highlight effects. Styles: "ring" (pulsing border), "spotlight" (dims page except element), "focus" (both combined)
- `clear_spotlight()` - Remove all spotlight effects

**Phase 3: Camera Control**
- `camera_zoom(selector, level?, duration_ms?)` - Zoom into element using CSS transforms (Ken Burns effect). Level: 1.0=normal, 1.5=50% zoom, 2.0=100% zoom
- `camera_pan(selector, duration_ms?)` - Pan to center on element without zooming
- `camera_reset(duration_ms?)` - Reset camera to normal 1.0 scale view

**Phase 4: Post-Production** (requires ffmpeg - use via shell to avoid MCP timeouts)
- `check_environment()` - Verify ffmpeg installation, API keys, and get ffmpeg command examples! Returns workflow guide with copy-paste commands.
- `get_video_duration(path)` - Get video duration in seconds/milliseconds
- `list_stock_music(query?, tags?, instrumental?, speed?, min_duration?, max_duration?, client_id?)` - Search Jamendo for CC-licensed music (pass client_id or set JAMENDO_CLIENT_ID env)
- `download_stock_music(url, output?, filename?)` - Download a stock music track to local cache

**Use ffmpeg directly via shell for video processing:**
```bash
# Convert WebM to MP4
ffmpeg -i recording.webm -c:v libx264 -preset fast -crf 23 output.mp4

# Add voiceover
ffmpeg -i video.mp4 -i voiceover.mp3 -c:v copy -c:a aac -shortest output.mp4

# Add background music (15% volume)
ffmpeg -i video.mp4 -i music.mp3 -filter_complex "[1:a]volume=0.15[bg];[0:a][bg]amix" -c:v copy output.mp4

# Add text overlay
ffmpeg -i video.mp4 -vf "drawtext=text='Title':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" output.mp4
```

**Phase 5: Polish**
- `smooth_scroll(direction, amount?, duration_ms?)` - Cinematic smooth scrolling with easing (vs instant jump)
- `type_human(selector, text, wpm?, variance?)` - Human-like typing with variable speed and pauses after punctuation
- `set_presentation_mode(enabled)` - Hide scrollbars and enable smooth scroll CSS for cleaner video
- `freeze_time(timestamp?)` - Mock Date.now() to show consistent timestamps in demos

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
find_relative("text=Total Gain", "below", "text")  // Find value below label (recommended)
// "text" mode finds nearest leaf text element, avoiding container elements
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

### Get page state with text content
```
page_state(include_text=True)  // Get elements + text summary
// Returns: interactive_elements[], text_summary: {headings[], key_text[]}
// Useful when you need both clickable elements AND page content
```

### Generate voiceover for video (Cinematic Engine)
```
// Generate voiceover audio file (OpenAI TTS)
result = generate_voiceover("Welcome to our product demo", voice="nova")
audio_path = result["data"]["path"]

// Get audio duration to pace video actions
duration = get_audio_duration(audio_path)
// Returns: {"duration_ms": 3500, "duration_sec": 3.5}
// Use duration_ms to time your cursor movements and scrolling
```

### Record a demo video with cursor animation (Cinematic Engine)
```
// 1. Navigate to your app first
goto("https://example.com")

// 2. Start recording (virtual cursor injected but off-screen)
start_recording(width=1920, height=1080)

// 3. Move cursor to element (MANUAL - for cinematic control)
evaluate("window.__agentCursor.moveTo(500, 300, 800)")  // x, y, duration_ms
wait(1000)  // Let animation complete

// 4. Show click effect and perform action
evaluate("window.__agentCursor.click(500, 300)")  // Ripple effect
click("#login-btn")

// 5. Add callout annotation
annotate("Enter your email here", target="#email", position="above", style="dark")

// 6. Move cursor to next element
evaluate("window.__agentCursor.moveTo(600, 400, 600)")
wait(700)
fill("#email", "user@example.com")

// 7. Stop and get video path
result = stop_recording()
// Returns: {"path": "/videos/xxx.webm", "duration_sec": 5.2}
```

**Cursor API (via evaluate):**
- `window.__agentCursor.moveTo(x, y, duration_ms)` - Smooth move to position
- `window.__agentCursor.click(x, y)` - Show click ripple effect
- `window.__agentCursor.hide()` / `show()` - Toggle visibility

### Cinematic camera effects (Cinematic Engine)
```
// Zoom into an element (Ken Burns effect)
camera_zoom("header", level=1.5, duration_ms=1000)
wait(1200)  // Wait for animation

// Pan to another element
camera_pan("footer", duration_ms=800)
wait(900)

// Reset to normal view
camera_reset(duration_ms=600)
wait(700)
```

**Camera notes:**
- Camera uses CSS transforms, preserving responsive layouts (unlike viewport resize)
- Always wait for animation to complete before next action
- Combine with annotations for professional callout effects
- Works during video recording to create dynamic visuals

### Complete video production workflow (Cinematic Engine)
```
// ============================================
// PHASE 1: PREPARATION (do this first!)
// ============================================

// 1. Check environment
check_environment()
// Returns: {ffmpeg: true, elevenlabs_key: true, jamendo_key: true, errors: []}

// 2. Generate voiceover FIRST - timing drives everything
vo = generate_voiceover(
    text="Welcome to our product demo. Watch the key features in action.",
    voice="H2JKG8QcEaH9iUMauArc",   // Abhinav - warm, natural
    provider="elevenlabs",
    stability=0.35,                 // More expressive (less robotic)
    similarity_boost=0.6,           // Balanced clarity
    style=0.3                       // Some emotion
)
vo_duration = get_audio_duration(vo["data"]["path"])
// Know your audio is ~8 seconds - plan video actions accordingly

// 3. Find background music
tracks = list_stock_music(query="corporate inspiring", instrumental=true, speed="medium")
music = download_stock_music(url=tracks["data"]["tracks"][0]["download_url"])

// ============================================
// PHASE 2: RECORDING (visual capture)
// ============================================

start_recording(width=1920, height=1080)
set_presentation_mode(enabled=true)  // Hide scrollbars

// Navigate
goto("https://example.com")
wait(500)

// Add annotation callout
annotate("Welcome!", style="dark", position="top-right")
wait(2000)

// Spotlight with focus effect (ring + dim)
spotlight(selector="h1", style="focus", color="#3b82f6", dim_opacity=0.7)
wait(3000)
clear_spotlight()

// Camera zoom
camera_zoom(selector="h1", level=1.5, duration_ms=1000)
wait(1500)
camera_reset(duration_ms=800)
wait(500)

// Smooth scroll
clear_annotations()
smooth_scroll(direction="down", amount=300, duration_ms=1000)
wait(500)

// Ring highlight on content
spotlight(selector="p", style="ring", color="#10b981", pulse_ms=1200)
annotate("Key information", style="light", position="right")
wait(2000)

// Cleanup
clear_spotlight()
clear_annotations()
result = stop_recording()

// ============================================
// PHASE 3: POST-PRODUCTION (use ffmpeg via shell)
// ============================================
// NOTE: Use ffmpeg directly to avoid MCP timeout issues.
// check_environment() returns full ffmpeg command examples!

raw_video = result["data"]["path"]  // WebM from recording

// Run in shell (not as MCP tools):
// 1. Convert: ffmpeg -i recording.webm -c:v libx264 -preset fast output.mp4
// 2. Add voice: ffmpeg -i output.mp4 -i voice.mp3 -c:v copy -c:a aac final_with_voice.mp4
// 3. Add music: ffmpeg -i final_with_voice.mp4 -i music.mp3 -filter_complex "[1:a]volume=0.15[bg];[0:a][bg]amix" -c:v copy final.mp4
// 4. Add title: ffmpeg -i final.mp4 -vf "drawtext=text='Demo':fontsize=72:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" output.mp4
```

### Spotlight effects (Cinematic Engine)
```
// Ring: Glowing pulsing border around element
spotlight(selector="button.cta", style="ring", color="#3b82f6", pulse_ms=1500)

// Spotlight: Dims entire page except target element
spotlight(selector="#hero", style="spotlight", dim_opacity=0.7)

// Focus: Ring + spotlight combined (maximum impact)
spotlight(selector=".feature", style="focus", color="#10b981", dim_opacity=0.6)

// Always clear before applying new effect
clear_spotlight()
```

### Text overlays (ffmpeg via shell)
```bash
# Centered title (visible 0-4 seconds)
ffmpeg -i input.mp4 -vf "drawtext=text='Welcome to Our Demo':fontsize=64:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,4)'" -c:a copy with_title.mp4

# Bottom caption (visible 10-15 seconds)
ffmpeg -i with_title.mp4 -vf "drawtext=text='Key Feature':fontsize=36:fontcolor=white:x=(w-text_w)/2:y=h-50:enable='between(t,10,15)'" -c:a copy with_caption.mp4
```

### Multi-scene video concatenation (ffmpeg via shell)
```bash
# Record multiple scenes (produces scene1.webm, scene2.webm)
start_recording(width=1920, height=1080)
# ... scene 1 actions ...
stop_recording()

start_recording(width=1920, height=1080)
# ... scene 2 actions ...
stop_recording()

# Concatenate in shell:
# 1. Create list file
echo "file 'scene1.webm'" > list.txt
echo "file 'scene2.webm'" >> list.txt

# 2. Join clips
ffmpeg -f concat -safe 0 -i list.txt -c:v libx264 -c:a aac combined.mp4
```

**Cinematic Engine best practices:**
- **Generate voiceover first** - Audio duration determines video pacing
- **Use check_environment()** - Get ffmpeg command examples and verify setup
- **Use ffmpeg via shell** - Avoids MCP timeout issues with long operations
- **Use `-c:v copy`** - Skip video re-encoding when possible (much faster)
- **Use presentation mode** - Cleaner visuals without scrollbars
- **Wait after effects** - Let animations complete (wait > duration_ms)
- **Layer effects** - Combine spotlight + annotation for emphasis
- **Keep music subtle** - Use `volume=0.15` in ffmpeg for background music
- **Add titles in post** - Text overlays more flexible than annotations
- **Clear before switching** - Always clear_spotlight() before new spotlight

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
