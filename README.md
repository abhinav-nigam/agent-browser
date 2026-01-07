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

agent-browser provides **50 browser automation tools** organized into categories:

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
