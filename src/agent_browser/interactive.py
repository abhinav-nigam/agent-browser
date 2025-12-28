"""
Interactive Test Runner - Claude-in-the-Loop

This runner takes screenshots and saves them for Claude Code to analyze directly.
Claude then suggests actions, and you execute them through this script.

Usage:
    agent-browser interact http://localhost:5000/financial-journey/quick-start

Commands (type in console):
    screenshot / ss    - Take a screenshot for Claude to analyze
    click <selector>   - Click an element (e.g., click #submitBtn)
    type <sel> <text>  - Type text into element (e.g., type #userAge 30)
    fill <field> <val> - Fill a form field by name
    select <sel> <val> - Select dropdown option
    scroll <dir>       - Scroll up/down/top/bottom
    wait <ms>          - Wait milliseconds
    eval <js>          - Execute JavaScript
    url                - Print current URL
    quit / q           - Exit

The workflow:
1. Run this script
2. Type 'ss' to take a screenshot
3. Ask Claude Code to read the screenshot and suggest actions
4. Execute the suggested actions
5. Repeat until test is complete
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page

from .utils import PathTraversalError, sanitize_filename, validate_path


class InteractiveRunner:
    def __init__(
        self,
        start_url: str,
        headless: bool = False,
        session_id: str = "default",
        output_dir: Optional[Union[str, Path]] = None,
    ):
        self.start_url = start_url
        self.headless = headless
        self.session_id = sanitize_filename(session_id or "default")
        output_dir_path = Path(output_dir) if output_dir else Path("./screenshots/interactive")
        # Validate output_dir is within CWD to prevent path traversal
        try:
            self.output_dir = validate_path(output_dir_path)
        except PathTraversalError as e:
            raise ValueError(f"Invalid output directory: {e}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._playwright: Any = None
        self._browser: Optional["Browser"] = None
        self._page: Optional["Page"] = None
        self.screenshot_count = 0

    def start(self) -> None:
        """Start browser and navigate to URL."""
        from playwright.sync_api import sync_playwright

        print("Starting browser...")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=100,
        )
        context = self._browser.new_context(viewport={"width": 1280, "height": 900})
        self._page = context.new_page()

        print(f"Navigating to {self.start_url}")
        self._page.goto(self.start_url, wait_until="networkidle")
        print("Ready! Type 'ss' to take a screenshot, 'help' for commands.\n")

    def stop(self) -> None:
        """Stop browser."""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        print("Browser closed.")

    @property
    def page(self) -> "Page":
        if not self._page:
            raise RuntimeError("Browser page not initialized. Call start() first.")
        return self._page

    def screenshot(self, name: Optional[str] = None) -> str:
        """Take screenshot and return path."""
        self.screenshot_count += 1
        timestamp = datetime.now().strftime("%H%M%S")
        label = sanitize_filename(name) if name else sanitize_filename(timestamp)
        filename = f"step_{self.screenshot_count:02d}_{label}.png"
        filepath = self.output_dir / filename

        self.page.screenshot(path=str(filepath), full_page=True)
        print(f"\nScreenshot saved: {filepath}")
        print(f"Ask Claude to: Read {filepath}")
        return str(filepath)

    def execute_command(self, cmd: str) -> bool:
        """Execute a command, return False to quit."""
        parts = cmd.strip().split(maxsplit=2)
        if not parts:
            return True

        action = parts[0].lower()

        try:
            if action in ("screenshot", "ss"):
                name = parts[1] if len(parts) > 1 else None
                self.screenshot(name)

            elif action == "click":
                selector = parts[1]
                self.page.click(selector)
                print(f"Clicked: {selector}")

            elif action == "type":
                selector = parts[1]
                text = parts[2] if len(parts) > 2 else ""
                self.page.fill(selector, text)
                print(f"Typed '{text}' into {selector}")

            elif action == "fill":
                field = parts[1]
                value = parts[2] if len(parts) > 2 else ""
                filled = False
                for sel in [f"#{field}", f"[name='{field}']", f"[data-testid='{field}']"]:
                    try:
                        self.page.fill(sel, value, timeout=1000)
                        print(f"Filled {sel} with '{value}'")
                        filled = True
                        break
                    except Exception:
                        continue
                if not filled:
                    print(f"No matching selector found for field '{field}'")

            elif action == "select":
                selector = parts[1]
                value = parts[2] if len(parts) > 2 else ""
                self.page.select_option(selector, value)
                print(f"Selected '{value}' in {selector}")

            elif action == "scroll":
                direction = parts[1] if len(parts) > 1 else "down"
                if direction == "top":
                    self.page.evaluate("window.scrollTo(0, 0)")
                elif direction == "bottom":
                    self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                elif direction == "up":
                    self.page.evaluate("window.scrollBy(0, -500)")
                else:
                    self.page.evaluate("window.scrollBy(0, 500)")
                print(f"Scrolled {direction}")

            elif action == "wait":
                ms = int(parts[1]) if len(parts) > 1 else 1000
                self.page.wait_for_timeout(ms)
                print(f"Waited {ms}ms")

            elif action == "eval":
                js = cmd[5:].strip()
                if not js:
                    print("Error: JavaScript code required")
                    return True
                result = self.page.evaluate(js)
                print(f"Result: {result}")

            elif action == "url":
                print(f"Current URL: {self.page.url}")

            elif action == "clear":
                self.page.evaluate("localStorage.clear()")
                print("Cleared localStorage")

            elif action == "reload":
                self.page.reload(wait_until="networkidle")
                print("Page reloaded")

            elif action == "back":
                self.page.go_back()
                print("Navigated back")

            elif action == "goto":
                url = parts[1] if len(parts) > 1 else self.start_url
                self.page.goto(url, wait_until="networkidle")
                print(f"Navigated to {url}")

            elif action in ("quit", "q", "exit"):
                return False

            elif action == "help":
                print(__doc__)

            else:
                print(f"Unknown command: {action}. Type 'help' for available commands.")

        except Exception as exc:
            print(f"Error: {exc}")

        return True

    def run(self) -> None:
        """Start interactive loop, taking an initial screenshot."""
        try:
            self.start()
            self.screenshot("initial")

            while True:
                try:
                    cmd = input("\n> ").strip()
                    if not self.execute_command(cmd):
                        break
                except KeyboardInterrupt:
                    print("\nInterrupted")
                    break
                except EOFError:
                    break
        finally:
            self.stop()
