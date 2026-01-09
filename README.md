# agent-browser

Browser automation for AI agents. Control browsers via MCP (Model Context Protocol) or CLI.

[![PyPI version](https://badge.fury.io/py/ai-agent-browser.svg)](https://badge.fury.io/py/ai-agent-browser)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Installation

```bash
pip install ai-agent-browser
playwright install chromium
```

## Quick Start by AI Tool

Most AI coding assistants support MCP (Model Context Protocol). Add agent-browser to your tool's config and the AI handles everything automatically.

### Claude Code

```bash
claude mcp add agent-browser -- agent-browser-mcp --allow-private
```

Or manually edit `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "agent-browser-mcp",
      "args": ["--allow-private"]
    }
  }
}
```

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "agent-browser-mcp",
      "args": ["--allow-private"]
    }
  }
}
```

### Cursor

Edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "agent-browser-mcp",
      "args": ["--allow-private"]
    }
  }
}
```

### Windsurf

Edit `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "agent-browser-mcp",
      "args": ["--allow-private"]
    }
  }
}
```

### VS Code + Cline

Open Cline settings and add to MCP Servers:

```json
{
  "agent-browser": {
    "command": "agent-browser-mcp",
    "args": ["--allow-private"]
  }
}
```

### gemini-cli

Edit `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "agent-browser-mcp",
      "args": ["--allow-private"]
    }
  }
}
```

### OpenAI Codex CLI

```bash
codex --mcp-config mcp.json
```

Create `mcp.json` in your project:

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "agent-browser-mcp",
      "args": ["--allow-private"]
    }
  }
}
```

### Aider (CLI Mode)

Aider doesn't support MCP yet. Use CLI mode instead:

```bash
# Add to your aider config or prompt:
# "You can control a browser using agent-browser CLI commands"

# In one terminal, start the browser:
agent-browser start http://localhost:3000 --session dev

# Aider can then run commands like:
agent-browser cmd screenshot --session dev
agent-browser cmd click "#login" --session dev
agent-browser cmd fill "#email" "test@example.com" --session dev
```

### Other MCP Clients

For any MCP-compatible client, the server command is:

```bash
agent-browser-mcp [OPTIONS]

Options:
  --allow-private  Allow localhost/private IPs (for local development)
  --visible        Show browser window (for debugging)
```

## What Can It Do?

agent-browser provides **74 browser automation tools** organized into categories:

| Category | Tools | Examples |
|----------|-------|----------|
| **Navigation** | 5 | `goto`, `back`, `forward`, `reload`, `get_url` |
| **Interactions** | 9 | `click`, `fill`, `type`, `select`, `press`, `hover`, `upload` |
| **Waiting** | 6 | `wait_for`, `wait_for_text`, `wait_for_url`, `wait_for_change` |
| **Data Extraction** | 6 | `screenshot`, `text`, `value`, `attr`, `count`, `evaluate` |
| **Assertions** | 3 | `assert_visible`, `assert_text`, `assert_url` |
| **Page State** | 5 | `scroll`, `viewport`, `cookies`, `storage`, `clear` |
| **Debugging** | 3 | `console`, `network`, `dialog` |
| **Agent Utilities** | 7 | `page_state`, `validate_selector`, `suggest_next_actions`, `browser_status` |
| **Perception** | 3 | `get_page_markdown`, `get_accessibility_tree`, `find_relative` |
| **Advanced** | 3 | `highlight`, `mock_network`, `clear_mocks` |
| **Video Production** | 24 | `start_recording`, `generate_voiceover`, `spotlight`, `add_text_overlay`, `camera_zoom` |

**For AI agents**: See [AGENT.md](AGENT.md) for a concise reference with selector syntax, common patterns, and tool safety levels.

## Feature Showcase

| **Research & Extraction** | **Cross-Page Audits** | **Data Operations** |
| :--- | :--- | :--- |
| ![Claude Demo](demo_claude_research.gif) | ![Gemini Demo](demo_gemini_audit.gif) | ![Interpreter Demo](demo_interpreter_data.gif) |
| *Autonomous web research* | *Multi-page analysis* | *Table scraping to structured data* |

## Common Use Cases

### Test a Local Web App

```
You: "Test the login flow on my React app at localhost:3000"

AI: I'll test the login flow for you.
    [navigates to localhost:3000]
    [takes screenshot of login page]
    [fills email and password fields]
    [clicks submit button]
    [waits for dashboard to load]
    [asserts URL contains /dashboard]
    [takes screenshot of result]

    Login flow works correctly. The user is redirected to /dashboard after successful login.
```

### Scrape Data from a Website

```
You: "Extract the product names and prices from this page"

AI: I'll extract the product data.
    [uses get_page_markdown to read structured content]
    [or uses evaluate to run JavaScript extraction]

    Found 24 products:
    - Product A: $29.99
    - Product B: $49.99
    ...
```

### Debug a Visual Issue

```
You: "The submit button isn't visible on mobile viewport"

AI: Let me check that.
    [sets viewport to 375x667 (iPhone)]
    [navigates to the page]
    [uses validate_selector to check button exists]
    [uses highlight to show button location]
    [takes screenshot]

    The button exists but is positioned off-screen. Here's a screenshot
    with the button highlighted. The CSS needs adjustment for mobile.
```

### Create a Marketing Video

```
You: "Create a demo video of our checkout flow with voiceover"

AI: I'll create a marketing video with narration.
    [generates voiceovers for each scene]
    [starts recording at 1920x1080]
    [navigates to checkout page]
    [moves cursor smoothly to cart button]
    [adds annotation "Click to checkout"]
    [camera zooms into form fields]
    [fills form with human-like typing]
    [stops recording]
    [merges video with voiceover audio]

    Created checkout_demo.mp4 (45 seconds) with synchronized narration.
```

## Cinematic Engine (Video Production)

Create marketing-grade videos with AI-controlled browser recordings, voiceovers, and post-production.

### Installation

```bash
pip install ai-agent-browser[video]
```

**Requirements:**
- `ffmpeg` installed (for video processing) - https://ffmpeg.org/
- `ELEVENLABS_API_KEY` for high-quality voiceover (recommended)
- `OPENAI_API_KEY` for OpenAI TTS (alternative)
- `JAMENDO_CLIENT_ID` for royalty-free music - https://devportal.jamendo.com/

### Capabilities

| Phase | Tools | Description |
|-------|-------|-------------|
| **Voice & Timing** | `generate_voiceover`, `get_audio_duration` | Generate TTS audio, get timing for sync |
| **Recording** | `start_recording`, `stop_recording`, `recording_status` | Capture video with virtual cursor |
| **Annotations** | `annotate`, `clear_annotations` | Floating text callouts |
| **Spotlight Effects** | `spotlight`, `clear_spotlight` | Ring highlights, spotlight dimming, focus effects |
| **Camera** | `camera_zoom`, `camera_pan`, `camera_reset` | Ken Burns-style zoom/pan effects |
| **Post-Production** | `merge_audio_video`, `add_background_music`, `add_text_overlay`, `concatenate_videos` | Audio mixing, titles, transitions |
| **Stock Music** | `list_stock_music`, `download_stock_music` | Royalty-free music from Jamendo |
| **Polish** | `smooth_scroll`, `type_human`, `set_presentation_mode` | Human-like interactions |

### Complete Workflow Example

```python
# ============================================
# PHASE 1: PREPARATION
# ============================================

# Check environment
check_environment()  # Verify ffmpeg, API keys

# Generate voiceover FIRST (timing drives everything)
vo = generate_voiceover(
    text="Welcome to our product. Watch as we explore the key features.",
    voice="21m00Tcm4TlvDq8ikWAM",  # ElevenLabs Rachel voice
    provider="elevenlabs"
)
vo_duration = get_audio_duration(vo["data"]["path"])  # ~8 seconds

# Find background music
tracks = list_stock_music(query="corporate inspiring", instrumental=True, speed="medium")
music = download_stock_music(url=tracks["data"]["tracks"][0]["download_url"])

# ============================================
# PHASE 2: RECORDING
# ============================================

# Start recording at 1080p
start_recording(width=1920, height=1080)
set_presentation_mode(enabled=True)  # Hide scrollbars

# Navigate and add welcome annotation
goto("https://example.com")
wait(500)
annotate("Welcome!", style="dark", position="top-right")
wait(2000)

# Spotlight the main heading with focus effect
spotlight(selector="h1", style="focus", color="#3b82f6", dim_opacity=0.7)
wait(3000)
clear_spotlight()

# Camera zoom on heading
camera_zoom(selector="h1", level=1.5, duration_ms=1000)
wait(1500)
camera_reset(duration_ms=800)
wait(500)

# Smooth scroll and highlight content
clear_annotations()
smooth_scroll(direction="down", amount=300, duration_ms=1000)
wait(500)

# Ring highlight on paragraph
spotlight(selector="p", style="ring", color="#10b981", pulse_ms=1200)
annotate("Key information here", style="light", position="right")
wait(2000)

# Cleanup and stop
clear_spotlight()
clear_annotations()
stop_result = stop_recording()

# ============================================
# PHASE 3: POST-PRODUCTION
# ============================================

raw_video = stop_result["data"]["path"]

# Merge voiceover (starts at 1 second)
merge_audio_video(
    video=raw_video,
    audio_tracks=[{"path": vo["data"]["path"], "start_ms": 1000}],
    output="videos/with_voice.mp4"
)

# Add background music (15% volume, auto-fades)
add_background_music(
    video="videos/with_voice.mp4",
    music=music["data"]["path"],
    output="videos/with_music.mp4",
    music_volume=0.15,      # 15% - subtle background
    voice_volume=1.3,       # 130% - boost voice clarity
    fade_in_sec=2.0,
    fade_out_sec=3.0
)

# Add title overlay
add_text_overlay(
    video="videos/with_music.mp4",
    text="Product Demo",
    output="videos/final.mp4",
    position="center",
    start_sec=0,
    end_sec=3,
    font_size=72,
    font_color="white",
    bg_color="black@0.7",
    fade_in_sec=0.8,
    fade_out_sec=0.8
)

# Result: Professional 1080p video with voiceover, music, and title
```

### Spotlight Effects

Draw attention to elements with cinematic highlighting:

```python
# Ring: Glowing pulsing border
spotlight(selector="button.cta", style="ring", color="#3b82f6", pulse_ms=1500)

# Spotlight: Dims everything except the element
spotlight(selector="#hero-title", style="spotlight", dim_opacity=0.7)

# Focus: Ring + spotlight combined (maximum impact)
spotlight(selector=".feature-card", style="focus", color="#10b981", dim_opacity=0.6)

# Clear all effects
clear_spotlight()
```

### Text Overlays

Add titles, captions, and annotations in post-production:

```python
# Centered title with fade
add_text_overlay(
    video="input.mp4",
    text="Welcome to Our Demo",
    output="with_title.mp4",
    position="center",      # top, center, bottom
    start_sec=0,
    end_sec=4,
    font_size=64,
    font_color="white",
    bg_color="black@0.6",   # Semi-transparent background
    fade_in_sec=0.5,
    fade_out_sec=0.5
)
```

### Video Transitions

Join multiple clips with professional transitions:

```python
# Concatenate with crossfade
concatenate_videos(
    videos=["scene1.mp4", "scene2.mp4", "scene3.mp4"],
    output="combined.mp4",
    transition="fade",       # fade, wipe, slide, dissolve
    transition_duration_sec=1.0
)
```

### Virtual Cursor

The recording includes a virtual cursor with smooth, human-like movement:

```javascript
// Cursor is controlled via JavaScript injection
window.__agentCursor.moveTo(x, y, duration_ms)  // Smooth move
window.__agentCursor.click(x, y)                 // Click with ripple effect
```

The cursor uses cubic-bezier easing for natural motion, not robotic linear movement.

### Best Practices

1. **Generate voiceover first** - Audio duration drives video pacing
2. **Use presentation mode** - Hides scrollbars for cleaner visuals
3. **Wait after effects** - Let animations complete before next action
4. **Layer effects** - Combine spotlight + annotation for maximum impact
5. **Keep music subtle** - 10-15% volume, let voice dominate
6. **Add titles in post** - Text overlays are more flexible than annotations

See `examples/cinematic_full_demo.py` for a complete working example.

## Security Features

agent-browser is designed for safe use with AI agents:

- **SSRF Protection**: Blocks dangerous schemes (`file://`, `javascript://`, `data://`) and private IPs by default
- **DNS Rebinding Protection**: Resolved IPs are validated against private ranges
- **Cloud Metadata Protection**: Blocks AWS/GCP metadata endpoints (169.254.169.254)
- **Path Sandboxing**: File operations restricted to working directory
- **Credential Rejection**: URLs with embedded `user:pass` are blocked
- **Sensitive Field Masking**: Password fields masked in `page_state` output

Use `--allow-private` only when testing local development servers.

## Advanced Configuration

### Dual Instances (Headless + Visible)

Run two browser instances - one for speed, one for debugging:

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "agent-browser-mcp",
      "args": ["--allow-private"]
    },
    "agent-browser-visible": {
      "command": "agent-browser-mcp",
      "args": ["--allow-private", "--visible"]
    }
  }
}
```

### Configuration Options

| Use Case | Args |
|----------|------|
| Production (SSRF protected) | `[]` |
| Local development | `["--allow-private"]` |
| Debugging (visible browser) | `["--allow-private", "--visible"]` |

## CLI Mode

For tools that don't support MCP, or for scripting:

### Basic Usage

```bash
# Terminal 1: Start browser (blocks while running)
agent-browser start http://localhost:8080

# Terminal 2: Send commands
agent-browser cmd screenshot home
agent-browser cmd click "#submit"
agent-browser cmd fill "#email" "test@example.com"
agent-browser cmd assert_visible ".success"

# When done
agent-browser stop
```

### Session Management

Run multiple browsers concurrently:

```bash
# Start separate sessions
agent-browser start http://localhost:3000 --session app1
agent-browser start http://localhost:4000 --session app2

# Commands target specific sessions
agent-browser cmd screenshot --session app1
agent-browser cmd click "#btn" --session app2

# Stop individually
agent-browser stop --session app1
```

### Interactive Mode

REPL for manual testing:

```bash
agent-browser interact http://localhost:8080

> screenshot initial
> click #login
> fill #email "test@example.com"
> assert_visible .dashboard
> quit
```

### CLI Command Reference

<details>
<summary>Click to expand full CLI reference</summary>

#### Browser Control
| Command | Description |
|---------|-------------|
| `start <url>` | Start browser session |
| `start <url> --visible` | Start with visible window |
| `stop` | Close browser |
| `status` | Check if browser running |

#### Navigation
| Command | Description |
|---------|-------------|
| `cmd goto <url>` | Navigate to URL |
| `cmd back` | Go back |
| `cmd forward` | Go forward |
| `cmd reload` | Reload page |

#### Interactions
| Command | Description |
|---------|-------------|
| `cmd click <selector>` | Click element |
| `cmd fill <selector> <text>` | Fill input |
| `cmd type <selector> <text>` | Type with key events |
| `cmd select <selector> <value>` | Select dropdown |
| `cmd press <key>` | Press key (Enter, Tab, etc.) |
| `cmd scroll <direction>` | Scroll (up/down/top/bottom) |

#### Screenshots & Data
| Command | Description |
|---------|-------------|
| `cmd screenshot [name]` | Take screenshot |
| `cmd text <selector>` | Get text content |
| `cmd value <selector>` | Get input value |
| `cmd count <selector>` | Count elements |

#### Assertions
| Command | Description |
|---------|-------------|
| `cmd assert_visible <sel>` | Check visibility |
| `cmd assert_text <sel> <text>` | Check text content |
| `cmd assert_url <pattern>` | Check URL |

#### Debugging
| Command | Description |
|---------|-------------|
| `cmd console` | View JS console |
| `cmd network` | View network log |
| `cmd wait <ms>` | Wait milliseconds |
| `cmd wait_for <selector>` | Wait for element |

</details>

## Architecture

```
┌─────────────────┐      MCP/JSON-RPC       ┌─────────────────┐
│   AI Assistant  │ ◄──────────────────────►│  agent-browser  │
│ (Claude, Cursor,│                         │   MCP Server    │
│  Gemini, etc.)  │                         │                 │
└─────────────────┘                         └────────┬────────┘
                                                     │
                                                     ▼
                                            ┌─────────────────┐
                                            │   Playwright    │
                                            │   (Chromium)    │
                                            └─────────────────┘
```

The MCP server manages browser lifecycle automatically. For CLI mode, a file-based IPC system coordinates between the CLI process and a persistent browser process.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Private IP blocked" | Add `--allow-private` for localhost testing |
| "Element not found" | Use `validate_selector` to check selector |
| "Timeout waiting" | Increase timeout or use `wait_for` first |
| Browser not responding | Check `browser_status` or restart |
| MCP not connecting | Verify config path and restart AI tool |

## Python API

```python
from agent_browser import BrowserDriver

driver = BrowserDriver(session_id="test")
result = driver.send_command("screenshot home")
print(result)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.
