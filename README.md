# agent-browser

A robust browser automation tool designed for AI agents to control browsers via CLI commands.

[![PyPI version](https://badge.fury.io/py/ai-agent-browser.svg)](https://badge.fury.io/py/ai-agent-browser)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

## 🎬 Feature Showcase

| **The Researcher (Claude)** | **The Architect (Gemini)** | **The Data Op (Interpreter)** |
| :--- | :--- | :--- |
| ![Claude Demo](demo_claude_research.gif) | ![Gemini Demo](demo_gemini_audit.gif) | ![Interpreter Demo](demo_interpreter_data.gif) |
| *Autonomous research & data extraction.* | *Cross-page architectural audits.* | *Complex table scraping to structured data.* |

## How to use this with Claude Code / Aider / ChatGPT

Copy-paste this prompt to let your AI pair-programmer drive `agent-browser` safely:

```
You can run shell commands on my machine. Use `agent-browser start <url> --session <name>` to launch a browser, then `agent-browser cmd <action> --session <name>` for steps like `screenshot`, `click`, `fill`, `assert_visible`, and `wait_for`. Keep sessions isolated by always passing `--session <name>` and stop them with `agent-browser stop --session <name>` when done. Screenshots land in ./screenshots. Avoid writing outside the project; use relative paths only. If you need to upload a file, ask me for the path first.
```

## Why This Exists

AI agents (like Claude Code, Codex, GPT-based tools) need to interact with web applications for testing and automation. However, most browser automation tools require:
- Programmatic API access within a running process
- Complex async/await patterns
- Persistent connections

**agent-browser** solves this by providing:
- **Simple CLI commands** - Any process that can run shell commands can control a browser
- **File-based IPC** - Stateless CLI commands control a stateful browser session
- **Multi-session support** - Run multiple browser sessions concurrently
- **Built for AI** - Screenshots auto-resize for vision models, assertions return clear PASS/FAIL
- **MCP Server** - Native Model Context Protocol support for Claude Desktop and other MCP clients

## Installation

```bash
pip install ai-agent-browser
playwright install chromium
```

## Quick Start

```bash
# Terminal 1: Start browser (blocks while running)
agent-browser start http://localhost:8080

# Terminal 2: Send commands
agent-browser cmd screenshot home
agent-browser cmd click "button[type='submit']"
agent-browser cmd fill "#email" "test@example.com"
agent-browser cmd assert_visible ".success-message"

# When done
agent-browser stop
```

## Security Features

- **Path traversal protection** on file paths (screenshots, uploads) to keep writes inside allowed directories.
- **Session isolation** via explicit `--session` flags so concurrent agents stay sandboxed from each other.
- **SSRF Protection** - URL validation blocks dangerous schemes (file://, javascript://, data://) and private IP ranges.
- **DNS rebinding protection** - Resolved IPs are checked against private ranges to prevent attacks.

## MCP Server (Model Context Protocol)

agent-browser includes a built-in MCP server for direct integration with Claude Desktop and other MCP-compatible AI assistants.

### Starting the MCP Server

```bash
# Start the MCP server (headless by default)
agent-browser-mcp

# Start with visible browser for debugging
agent-browser-mcp --visible

# Allow navigation to localhost/private IPs (for local development)
agent-browser-mcp --allow-private
```

### Claude Code CLI Configuration

Add the MCP server to Claude Code:

```bash
# For local development (allows localhost access)
claude mcp add agent-browser -- agent-browser-mcp --allow-private

# For production use (blocks private IPs for SSRF protection)
claude mcp add agent-browser -- agent-browser-mcp

# With visible browser for debugging
claude mcp add agent-browser -- agent-browser-mcp --allow-private --visible
```

Verify it's connected:

```bash
claude mcp list
# Should show: agent-browser: agent-browser-mcp --allow-private - ✓ Connected
```

### Claude Desktop Configuration

Add to your Claude Desktop config (`claude_desktop_config.json`):

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

### Available MCP Tools

The MCP server exposes 36 browser automation tools:

#### Navigation
| Tool | Parameters | Description |
|------|------------|-------------|
| `goto` | `url` | Navigate to URL (with SSRF protection) |
| `back` | - | Navigate back |
| `forward` | - | Navigate forward |
| `reload` | - | Reload current page |
| `get_url` | - | Get current page URL |

#### Interactions
| Tool | Parameters | Description |
|------|------------|-------------|
| `click` | `selector` | Click an element |
| `click_nth` | `selector`, `index` | Click the nth matching element |
| `fill` | `selector`, `value` | Fill a form field |
| `type` | `selector`, `text` | Type text with key events |
| `select` | `selector`, `value` | Select dropdown option |
| `hover` | `selector` | Hover over element |
| `focus` | `selector` | Focus an element |
| `press` | `key` | Press keyboard key (Enter, Tab, Escape, etc.) |
| `upload` | `selector`, `file_path` | Upload file to input |

#### Waiting
| Tool | Parameters | Description |
|------|------------|-------------|
| `wait` | `duration_ms` | Wait for milliseconds |
| `wait_for` | `selector`, `timeout_ms` | Wait for element to appear |
| `wait_for_text` | `text`, `timeout_ms` | Wait for text to appear |
| `wait_for_url` | `pattern`, `timeout_ms` | Wait for URL to contain pattern |
| `wait_for_load_state` | `state` | Wait for load/domcontentloaded/networkidle |

#### Data Extraction
| Tool | Parameters | Description |
|------|------------|-------------|
| `screenshot` | `name` (optional) | Take full-page screenshot |
| `text` | `selector` | Get element's text content |
| `value` | `selector` | Get input field value |
| `attr` | `selector`, `attribute` | Get element attribute |
| `count` | `selector` | Count matching elements |
| `evaluate` | `script` | Execute JavaScript |

#### Assertions
| Tool | Parameters | Description |
|------|------------|-------------|
| `assert_visible` | `selector` | Check if element is visible [PASS/FAIL] |
| `assert_text` | `selector`, `expected` | Check if element contains text [PASS/FAIL] |
| `assert_url` | `pattern` | Check if URL contains pattern [PASS/FAIL] |

#### Page State
| Tool | Parameters | Description |
|------|------------|-------------|
| `scroll` | `direction` | Scroll: up/down/top/bottom |
| `viewport` | `width`, `height` | Set viewport size |
| `cookies` | - | Get all cookies |
| `storage` | - | Get localStorage |
| `clear` | - | Clear localStorage and sessionStorage |

#### Debugging
| Tool | Parameters | Description |
|------|------------|-------------|
| `console` | - | Get console logs |
| `network` | - | Get network request logs |
| `dialog` | `action`, `prompt_text` | Handle JS dialogs (accept/dismiss) |

### MCP Security

The MCP server includes robust security features:

- **Blocked schemes**: `file://`, `javascript://`, `data://`, `chrome://`, `ftp://`, and more
- **Private IP blocking**: 10.x.x.x, 172.16-31.x.x, 192.168.x.x, 127.x.x.x, and link-local ranges
- **Cloud metadata protection**: Blocks 169.254.169.254 and metadata.google.internal
- **DNS validation**: Resolved IPs are checked against private ranges
- **Credential rejection**: URLs with embedded user:pass credentials are rejected
- **Path sandboxing**: File uploads are restricted to the working directory

Use `--allow-private` only for local development when you need to access localhost services.

## Architecture

```
+-------------------+       +----------------------+       +------------------+
| AI Agent / LLM    | <-->  | CLI + IPC files      | <-->  | Browser (PW)     |
| (Claude, Codex)   |       | cmd.json / result    |       | Chromium/Playwr. |
+-------------------+       +----------------------+       +------------------+
```

The browser runs in one process, listening for commands via JSON files. CLI commands write to `cmd.json`, the browser processes them and writes results to `result.json`. This decoupled architecture allows any process to control the browser.

## Command Reference

### Browser Control

| Command | Description | Example |
|---------|-------------|---------|
| `start <url>` | Start browser session (blocks) | `agent-browser start http://localhost:8080` |
| `start <url> --visible` | Start in headed mode | `agent-browser start http://localhost:8080 --visible` |
| `stop` | Close browser | `agent-browser stop` |
| `status` | Check if browser is running | `agent-browser status` |
| `cmd reload` | Reload current page | `agent-browser cmd reload` |
| `cmd goto <url>` | Navigate to URL | `agent-browser cmd goto http://example.com` |
| `cmd back` | Navigate back | `agent-browser cmd back` |
| `cmd forward` | Navigate forward | `agent-browser cmd forward` |
| `cmd url` | Print current URL | `agent-browser cmd url` |
| `cmd viewport <w> <h>` | Set viewport size | `agent-browser cmd viewport 1920 1080` |

### Screenshots

| Command | Description | Example |
|---------|-------------|---------|
| `cmd screenshot [name]` | Full-page screenshot | `agent-browser cmd screenshot checkout_page` |
| `cmd screenshot viewport [name]` | Viewport only (faster) | `agent-browser cmd screenshot viewport header` |
| `cmd ss [name]` | Alias for screenshot | `agent-browser cmd ss step1` |

Screenshots are automatically resized to max 1500x1500 for AI vision model compatibility.

### Interactions

| Command | Description | Example |
|---------|-------------|---------|
| `cmd click <selector>` | Click element | `agent-browser cmd click "#submit-btn"` |
| `cmd click_nth <selector> <n>` | Click nth element (0-indexed) | `agent-browser cmd click_nth ".item" 2` |
| `cmd fill <selector> <text>` | Fill input field | `agent-browser cmd fill "#email" "test@example.com"` |
| `cmd type <selector> <text>` | Type with key events | `agent-browser cmd type "#search" "query"` |
| `cmd select <selector> <value>` | Select dropdown option | `agent-browser cmd select "#country" "US"` |
| `cmd press <key>` | Press keyboard key | `agent-browser cmd press Enter` |
| `cmd scroll <direction>` | Scroll page | `agent-browser cmd scroll down` |
| `cmd hover <selector>` | Hover over element | `agent-browser cmd hover ".tooltip-trigger"` |
| `cmd focus <selector>` | Focus element | `agent-browser cmd focus "#input"` |
| `cmd upload <selector> <path>` | Upload file | `agent-browser cmd upload "#file" ./doc.pdf` |
| `cmd dialog <action> [text]` | Handle dialog | `agent-browser cmd dialog accept` |
| `cmd clear` | Clear localStorage/sessionStorage | `agent-browser cmd clear` |

**Scroll directions:** `up`, `down`, `top`, `bottom`, `left`, `right`

**Dialog actions:** `accept`, `dismiss`, `accept <prompt_text>`

### Assertions

All assertions return `[PASS]` or `[FAIL]` prefix for easy parsing.

| Command | Description | Example |
|---------|-------------|---------|
| `cmd assert_visible <selector>` | Element is visible | `agent-browser cmd assert_visible ".modal"` |
| `cmd assert_hidden <selector>` | Element is hidden | `agent-browser cmd assert_hidden ".loading"` |
| `cmd assert_text <selector> <text>` | Element contains text | `agent-browser cmd assert_text ".msg" "Success"` |
| `cmd assert_text_exact <sel> <text>` | Text matches exactly | `agent-browser cmd assert_text_exact ".count" "42"` |
| `cmd assert_value <selector> <value>` | Input has value | `agent-browser cmd assert_value "#email" "test@example.com"` |
| `cmd assert_checked <selector>` | Checkbox is checked | `agent-browser cmd assert_checked "#agree"` |
| `cmd assert_url <pattern>` | URL contains pattern | `agent-browser cmd assert_url "/dashboard"` |

### Data Extraction

| Command | Description | Example |
|---------|-------------|---------|
| `cmd text <selector>` | Get text content | `agent-browser cmd text ".title"` |
| `cmd value <selector>` | Get input value | `agent-browser cmd value "#email"` |
| `cmd attr <selector> <attr>` | Get attribute | `agent-browser cmd attr "a" "href"` |
| `cmd count <selector>` | Count matching elements | `agent-browser cmd count ".item"` |
| `cmd eval <javascript>` | Execute JavaScript | `agent-browser cmd eval "document.title"` |
| `cmd cookies` | Get all cookies (JSON) | `agent-browser cmd cookies` |
| `cmd storage` | Get localStorage (JSON) | `agent-browser cmd storage` |

### Debugging

| Command | Description | Example |
|---------|-------------|---------|
| `cmd console` | View JS console logs | `agent-browser cmd console` |
| `cmd network` | View network requests | `agent-browser cmd network` |
| `cmd network_failed` | View failed requests | `agent-browser cmd network_failed` |
| `cmd clear_logs` | Clear console/network logs | `agent-browser cmd clear_logs` |
| `cmd wait <ms>` | Wait milliseconds | `agent-browser cmd wait 2000` |
| `cmd wait_for <selector> [ms]` | Wait for element | `agent-browser cmd wait_for ".loaded" 15000` |
| `cmd wait_for_text <text>` | Wait for text | `agent-browser cmd wait_for_text "Complete"` |
| `cmd help` | Show help | `agent-browser cmd help` |

### Flag Tips

- `cmd --timeout <seconds>` overrides the IPC wait when sending commands (e.g., `agent-browser cmd --timeout 30 wait_for ".loaded" 20000`).
- `interact --headless` runs the interactive REPL without opening a visible browser window (e.g., `agent-browser interact http://localhost:8080 --headless`).

## Session Management

Run multiple browser sessions concurrently using session IDs:

```bash
# Start two sessions
agent-browser start http://localhost:8080 --session app1
agent-browser start http://localhost:9090 --session app2

# Send commands to specific sessions
agent-browser cmd screenshot home --session app1
agent-browser cmd click "#login" --session app2

# Check status
agent-browser status --session app1

# Stop specific session
agent-browser stop --session app1
```

## Configuration

### Screenshot Output Directory

```bash
agent-browser start http://localhost:8080 --output-dir ./my-screenshots
```

### Timeouts

Default timeouts:
- **Command timeout:** 5 seconds (click, fill, etc.)
- **wait_for timeout:** 10 seconds (can override: `wait_for .element 15000`)
- **IPC timeout:** 10 seconds (waiting for browser response) — increase with `cmd --timeout <seconds>` if your action needs more time.

## Selectors

Use standard Playwright/CSS selectors:

```bash
# CSS selectors
agent-browser cmd click ".btn-primary"
agent-browser cmd click "#submit"
agent-browser cmd click "button[type='submit']"
agent-browser cmd click "[data-testid='login-btn']"

# Text selectors
agent-browser cmd click "text='Sign In'"
agent-browser cmd click "text=Submit"

# Chained selectors
agent-browser cmd click ".card >> text='Edit'"
```

## Interactive Mode

For manual testing with AI assistance:

```bash
agent-browser interact http://localhost:8080
```

Headless REPL run:

```bash
agent-browser interact http://localhost:8080 --headless
```

This starts a REPL where you can type commands directly:

```
> ss initial
Screenshot saved: ./screenshots/interactive/step_01_initial.png
> click #login
Clicked: #login
> ss after_login
Screenshot saved: ./screenshots/interactive/step_02_after_login.png
> quit
```

## Integration with AI Agents

### Claude Code Example

```bash
# In Claude Code conversation:
# "Test the login flow on localhost:8080"

# Claude runs:
agent-browser start http://localhost:8080 --session test1 &
sleep 2
agent-browser cmd screenshot login_page --session test1
# Claude analyzes screenshot...
agent-browser cmd fill "#username" "testuser" --session test1
agent-browser cmd fill "#password" "testpass" --session test1
agent-browser cmd click "button[type='submit']" --session test1
agent-browser cmd wait_for ".dashboard" --session test1
agent-browser cmd assert_url "/dashboard" --session test1
agent-browser cmd screenshot success --session test1
agent-browser stop --session test1
```

### Generic LLM Integration

```python
import subprocess

def browser_cmd(cmd: str, session: str = "default") -> str:
    result = subprocess.run(
        ["agent-browser", "cmd", *cmd.split(), "--session", session],
        capture_output=True, text=True
    )
    return result.stdout.strip()

# Start browser (in separate process)
subprocess.Popen(["agent-browser", "start", "http://localhost:8080", "--session", "test"])

# Send commands
browser_cmd("screenshot initial", "test")
browser_cmd("click #login", "test")
browser_cmd("assert_visible .dashboard", "test")
```

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| State | `%TEMP%/agent_browser_{session}_state.json` | Browser running state |
| Commands | `%TEMP%/agent_browser_{session}_cmd.json` | Pending command |
| Results | `%TEMP%/agent_browser_{session}_result.json` | Command result |
| Console logs | `%TEMP%/agent_browser_{session}_console.json` | JS console output |
| Network logs | `%TEMP%/agent_browser_{session}_network.json` | Network requests |
| Screenshots | `./screenshots/` (configurable) | Captured screenshots |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Timeout waiting for result` | Browser may have crashed - run `status` to check |
| `Element not found` | Use `count` to verify selector matches elements |
| `Browser not responding` | Run `status` to ping the browser |
| `Browser process has died` | State was stale - run `start <url>` to restart |
| `Complex selector failing` | Use `eval` with JavaScript as fallback |

### Debug Workflow

```bash
# 1. Check browser status
agent-browser status

# 2. Check for JS errors
agent-browser cmd console

# 3. Check for failed requests
agent-browser cmd network_failed

# 4. Take screenshot to see current state
agent-browser cmd screenshot debug

# 5. Count elements to verify selector
agent-browser cmd count ".my-selector"
```

## Python API

You can also use agent-browser as a Python library:

```python
from agent_browser import BrowserDriver

driver = BrowserDriver(session_id="test", output_dir="./screenshots")

# Start browser (blocking - run in thread/process)
# driver.start("http://localhost:8080")

# Or send commands to running browser
result = driver.send_command("screenshot home")
print(result)

status = driver.status()  # Returns True if running
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.
