#!/usr/bin/env python
"""
Basic example: Test a login flow using agent-browser.

This example demonstrates how to use agent-browser from Python code
to automate a simple login test.

Prerequisites:
    pip install agent-browser
    playwright install chromium

Usage:
    # First, start a web server with a login page (e.g., on localhost:8080)
    # Then run this script
    python basic_test.py
"""

import subprocess
import time


def run_cmd(cmd: str, session: str = "example") -> str:
    """Run an agent-browser command and return output."""
    result = subprocess.run(
        ["agent-browser", "cmd", *cmd.split(), "--session", session],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main():
    session = "login_test"
    url = "http://localhost:8080"  # Change to your app's URL

    print(f"Starting browser for {url}...")

    # Start browser in background
    browser_proc = subprocess.Popen(
        ["agent-browser", "start", url, "--session", session],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for browser to be ready
    time.sleep(3)

    try:
        # Take initial screenshot
        print(run_cmd("screenshot 01_login_page", session))

        # Fill in credentials
        print(run_cmd('fill "#username" testuser', session))
        print(run_cmd('fill "#password" testpass', session))
        print(run_cmd("screenshot 02_filled_form", session))

        # Click login button
        print(run_cmd('click "button[type=submit]"', session))

        # Wait for navigation
        print(run_cmd("wait 2000", session))

        # Verify we're on dashboard
        result = run_cmd("assert_url /dashboard", session)
        print(result)

        if "[PASS]" in result:
            print("\n*** LOGIN TEST PASSED ***")
        else:
            print("\n*** LOGIN TEST FAILED ***")

        # Take final screenshot
        print(run_cmd("screenshot 03_after_login", session))

    finally:
        # Stop browser
        print(run_cmd("stop", session))
        browser_proc.terminate()


if __name__ == "__main__":
    main()
