# Examples

This directory contains example scripts showing how to use agent-browser.

## Examples

### basic_test.py

A simple example showing how to automate a login flow:

```bash
python basic_test.py
```

### ai_agent_integration.py

Shows how an AI agent might use agent-browser in a loop:
1. Take screenshot
2. Analyze and decide action
3. Execute action
4. Repeat

```bash
python ai_agent_integration.py
```

## Prerequisites

1. Install agent-browser:
   ```bash
   pip install agent-browser
   playwright install chromium
   ```

2. Have a web application running (the examples assume `http://localhost:8080`)

## Running Examples

Each example starts its own browser session. Make sure no other agent-browser
sessions are running with the same session ID.
