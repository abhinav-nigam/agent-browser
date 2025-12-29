#!/usr/bin/env python
"""
AI Agent Integration Example

This example shows how an AI agent (like an LLM-powered tool) might use
agent-browser to interact with web pages.

The pattern:
1. Agent takes screenshot
2. Agent analyzes screenshot to decide next action
3. Agent executes action
4. Repeat until objective is achieved
"""

import subprocess
import time
from dataclasses import dataclass


@dataclass
class BrowserSession:
    """Wrapper for agent-browser commands."""

    session_id: str
    output_dir: str = "./screenshots"

    def cmd(self, command: str, timeout: int = 30) -> str:
        """Execute a browser command."""
        result = subprocess.run(
            ["agent-browser", "cmd", *command.split(), "--session", self.session_id],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()

    def screenshot(self, name: str) -> str:
        """Take a screenshot and return path."""
        return self.cmd(f"screenshot {name}")

    def click(self, selector: str) -> str:
        """Click an element."""
        return self.cmd(f'click "{selector}"')

    def fill(self, selector: str, text: str) -> str:
        """Fill a form field."""
        return self.cmd(f'fill "{selector}" "{text}"')

    def assert_visible(self, selector: str) -> bool:
        """Check if element is visible."""
        result = self.cmd(f'assert_visible "{selector}"')
        return "[PASS]" in result

    def assert_text(self, selector: str, text: str) -> bool:
        """Check if element contains text."""
        result = self.cmd(f'assert_text "{selector}" "{text}"')
        return "[PASS]" in result

    def get_text(self, selector: str) -> str:
        """Get text content of element."""
        return self.cmd(f'text "{selector}"')

    def wait_for(self, selector: str, timeout_ms: int = 10000) -> str:
        """Wait for element to appear."""
        return self.cmd(f'wait_for "{selector}" {timeout_ms}')


def simulate_ai_agent(browser: BrowserSession, objective: str):
    """
    Simulate an AI agent testing a web page.

    In a real implementation, you would:
    1. Take a screenshot
    2. Send to an LLM with the objective
    3. Parse the LLM's suggested action
    4. Execute the action
    5. Repeat until objective is achieved
    """
    print(f"Objective: {objective}")
    print("-" * 50)

    # Step 1: Take initial screenshot
    screenshot_path = browser.screenshot("01_initial")
    print(f"Screenshot: {screenshot_path}")

    # Step 2: AI would analyze screenshot and decide action
    # For this example, we'll simulate a simple form fill

    # Check what's on the page
    print("\nAnalyzing page...")
    if browser.assert_visible("#email"):
        print("Found email field - filling...")
        browser.fill("#email", "test@example.com")

    if browser.assert_visible("#password"):
        print("Found password field - filling...")
        browser.fill("#password", "securepass123")

    browser.screenshot("02_filled")

    # Step 3: Submit form
    if browser.assert_visible("button[type='submit']"):
        print("Found submit button - clicking...")
        browser.click("button[type='submit']")
        browser.wait_for(".success, .error, .dashboard", 5000)
        browser.screenshot("03_result")

    # Step 4: Check result
    if browser.assert_visible(".success"):
        print("\n*** OBJECTIVE ACHIEVED: Form submitted successfully ***")
    elif browser.assert_visible(".error"):
        error_text = browser.get_text(".error")
        print(f"\n*** ERROR: {error_text} ***")
    else:
        print("\n*** Unknown state - check screenshots ***")


def main():
    session_id = "ai_agent_demo"
    url = "http://localhost:8080"  # Change to your test app

    print(f"Starting browser at {url}...")

    # Start browser
    browser_proc = subprocess.Popen(
        ["agent-browser", "start", url, "--session", session_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(3)

    try:
        browser = BrowserSession(session_id=session_id)
        simulate_ai_agent(browser, "Fill out and submit the login form")

    finally:
        subprocess.run(
            ["agent-browser", "stop", "--session", session_id],
            capture_output=True,
        )
        browser_proc.terminate()


if __name__ == "__main__":
    main()
