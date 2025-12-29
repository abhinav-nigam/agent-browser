"""
MCP server entrypoint for agent-browser.

Provides a set of browser automation tools exposed through FastMCP, with
defensive URL validation and lightweight logging of console and network events.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import logging
import re
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from playwright.async_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Page,
    Request,
    Response,
    async_playwright,
)

from .utils import sanitize_filename, validate_path

LOGGER = logging.getLogger(__name__)

BLOCKED_SCHEMES = {
    "file",
    "data",
    "javascript",
    "chrome",
    "chrome-extension",
    "about",
    "view-source",
    "ws",
    "wss",
    "ftp",
    "blob",
    "vbscript",
    "mailto",
    "tel",
    "gopher",
    "vnc",
}

BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "169.254.169.254",
    "local",
    "internal",
    "localdomain",
}


class URLValidator:
    """
    Helpers for SSRF-safe URL validation.
    """

    _HOST_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")
    _PRIVATE_RANGES = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("fc00::/7"),
        ipaddress.ip_network("fe80::/10"),
        ipaddress.ip_network("100.64.0.0/10"),
    ]

    @staticmethod
    def is_private_ip(host: str) -> bool:
        """
        Return True if the host string represents a private or loopback IP.
        """

        try:
            ip_obj = ipaddress.ip_address(host)
        except ValueError:
            return False

        for network in URLValidator._PRIVATE_RANGES:
            if ip_obj in network:
                return True

        return bool(
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_reserved
            or ip_obj.is_link_local
        )

    @staticmethod
    def is_safe_url(url: str, allow_private: bool = False) -> bool:
        """
        Validate a URL for navigation, raising ValueError on unsafe targets.
        """

        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        if scheme in BLOCKED_SCHEMES:
            raise ValueError(f"Forbidden scheme: {scheme}")
        if scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported scheme: {scheme}")

        if parsed.username or parsed.password:
            raise ValueError("URLs containing credentials are not allowed")

        hostname = parsed.hostname or ""
        if not hostname or not URLValidator._HOST_PATTERN.match(hostname):
            raise ValueError("Invalid or missing hostname in URL")

        if allow_private:
            return True

        lowered = hostname.lower()
        if lowered in BLOCKED_HOSTS or lowered.endswith((".local", ".internal")):
            raise ValueError(f"Access to {hostname} is blocked")

        if URLValidator.is_private_ip(hostname):
            raise ValueError(f"Private IP targets are blocked: {hostname}")

        try:
            for info in socket.getaddrinfo(hostname, None):
                ip_value = str(info[4][0])
                if URLValidator.is_private_ip(ip_value):
                    raise ValueError(f"DNS resolved to private IP {ip_value}")
        except socket.gaierror:
            # Host could not be resolved; treat as unsafe
            raise ValueError(f"Unable to resolve host: {hostname}")

        return True


class BrowserServer:
    """
    FastMCP server wrapper exposing browser automation tools.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.server = FastMCP(name)
        self.playwright: Optional[Any] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.allow_private = False
        self.headless = True  # Set via configure() before run
        self.screenshot_dir = Path("screenshots")
        self.console_log: List[Dict[str, Any]] = []
        self.network_log: List[Dict[str, Any]] = []
        self._log_limit = 200
        self._lock = asyncio.Lock()
        self._started = False
        self._register_tools()

    def configure(self, allow_private: bool = False, headless: bool = True) -> None:
        """
        Configure server options before running.
        """
        self.allow_private = allow_private
        self.headless = headless

    def _register_tools(self) -> None:
        """
        Register tool methods with the FastMCP server.
        """

        # Navigation
        self.server.tool()(self.goto)
        self.server.tool()(self.back)
        self.server.tool()(self.forward)
        self.server.tool()(self.reload)
        self.server.tool()(self.get_url)

        # Interactions
        self.server.tool()(self.click)
        self.server.tool()(self.click_nth)
        self.server.tool()(self.fill)
        self.server.tool(name="type")(self.type_text)
        self.server.tool()(self.select)
        self.server.tool()(self.hover)
        self.server.tool()(self.focus)
        self.server.tool()(self.press)
        self.server.tool()(self.upload)

        # Waiting
        self.server.tool()(self.wait)
        self.server.tool()(self.wait_for)
        self.server.tool()(self.wait_for_text)
        self.server.tool()(self.wait_for_url)
        self.server.tool()(self.wait_for_load_state)

        # Data extraction
        self.server.tool()(self.screenshot)
        self.server.tool()(self.text)
        self.server.tool()(self.value)
        self.server.tool()(self.attr)
        self.server.tool()(self.count)
        self.server.tool()(self.evaluate)

        # Assertions
        self.server.tool()(self.assert_visible)
        self.server.tool()(self.assert_text)
        self.server.tool()(self.assert_url)

        # Page state
        self.server.tool()(self.scroll)
        self.server.tool()(self.viewport)
        self.server.tool()(self.cookies)
        self.server.tool()(self.storage)
        self.server.tool()(self.clear)

        # Debugging
        self.server.tool()(self.console)
        self.server.tool()(self.network)
        self.server.tool()(self.dialog)

    async def start(self, headless: bool = True) -> None:
        """
        Start Playwright and create a fresh browser context.
        """

        if self.playwright:
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.page = await self.context.new_page()
        self.context.on("console", self._handle_console)
        self.context.on(
            "requestfinished",
            lambda request: asyncio.create_task(self._handle_request_finished(request)),
        )
        self.context.on(
            "requestfailed",
            lambda request: asyncio.create_task(self._handle_request_failed(request)),
        )
        await self.page.goto("about:blank")

    async def stop(self) -> None:
        """
        Close the browser and release Playwright resources.
        """

        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.console_log.clear()
        self.network_log.clear()

    async def _ensure_page(self) -> Page:
        """
        Ensure Playwright is started and a page exists.
        Lazily initializes the browser on first call within the current event loop.
        """

        if not self._started:
            await self.start(headless=self.headless)
            self._started = True
        if not self.page:
            raise RuntimeError("Browser failed to start")
        return self.page

    def _record_console(self, message: ConsoleMessage) -> None:
        """
        Record a console event for later retrieval.
        """

        entry = {
            "type": message.type,
            "text": message.text,
            "location": str(message.location) if message.location else "",
        }
        self.console_log.append(entry)
        if len(self.console_log) > self._log_limit:
            self.console_log.pop(0)

    def _record_network(
        self,
        request: Request,
        response: Optional[Response],
        failure: Optional[str] = None,
    ) -> None:
        """
        Record a network event for later retrieval.
        """

        # Get failure info safely (request.failure is a property in Playwright async API)
        if failure is None:
            try:
                failure = request.failure
            except Exception:  # pylint: disable=broad-except
                failure = None

        entry: Dict[str, Any] = {
            "method": request.method,
            "url": request.url,
            "status": response.status if response else None,
            "failure": failure,
        }
        self.network_log.append(entry)
        if len(self.network_log) > self._log_limit:
            self.network_log.pop(0)

    def _handle_console(self, message: ConsoleMessage) -> None:
        """
        Console event hook for Playwright.
        """

        self._record_console(message)

    async def _handle_request_finished(self, request: Request) -> None:
        """
        Network event hook for completed requests.
        """

        try:
            response = await request.response()
        except Exception:  # pylint: disable=broad-except
            response = None
        self._record_network(request, response)

    async def _handle_request_failed(self, request: Request) -> None:
        """
        Network event hook for failed requests.
        """

        # request.failure is a property in Playwright async API
        self._record_network(request, None, failure=request.failure)

    async def goto(self, url: str) -> Dict[str, Any]:
        """
        Navigate to a safe URL after validation.
        """

        try:
            URLValidator.is_safe_url(url, allow_private=self.allow_private)
            async with self._lock:
                page = await self._ensure_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return {"success": True, "message": f"Navigated to {url}"}
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("Navigation failed")
            return {"success": False, "message": str(exc)}

    async def click(self, selector: str) -> Dict[str, Any]:
        """
        Click an element matching the selector.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.click(selector, timeout=10000)
            return {"success": True, "message": f"Clicked {selector}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def click_nth(self, selector: str, index: int) -> Dict[str, Any]:
        """
        Click the nth element matching the selector (0-indexed).
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                locator = page.locator(selector)
                count = await locator.count()
                if index < 0 or index >= count:
                    raise IndexError(f"Index {index} out of range (found {count})")
                await locator.nth(index).click(timeout=10000)
            return {"success": True, "message": f"Clicked {selector} at index {index}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def fill(self, selector: str, value: str) -> Dict[str, Any]:
        """
        Fill a form field.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.fill(selector, value, timeout=10000)
            return {"success": True, "message": f"Filled {selector}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def type_text(self, selector: str, text: str) -> Dict[str, Any]:
        """
        Type text into an element with key events.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.type(selector, text, delay=40, timeout=10000)
            return {"success": True, "message": f"Typed into {selector}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def select(self, selector: str, value: str) -> Dict[str, Any]:
        """
        Select an option in a dropdown.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.select_option(selector, value, timeout=10000)
            return {"success": True, "message": f"Selected {value} in {selector}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def hover(self, selector: str) -> Dict[str, Any]:
        """
        Hover over a selector.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.hover(selector, timeout=10000)
            return {"success": True, "message": f"Hovering over {selector}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def focus(self, selector: str) -> Dict[str, Any]:
        """
        Focus a selector.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.focus(selector, timeout=10000)
            return {"success": True, "message": f"Focused {selector}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def back(self) -> Dict[str, Any]:
        """
        Navigate back in history.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.go_back(wait_until="networkidle")
            return {"success": True, "message": "Navigated back"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def forward(self) -> Dict[str, Any]:
        """
        Navigate forward in history.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.go_forward(wait_until="networkidle")
            return {"success": True, "message": "Navigated forward"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def scroll(self, direction: str) -> Dict[str, Any]:
        """
        Scroll the current page.
        """

        scroll_map = {
            "top": "window.scrollTo(0, 0)",
            "bottom": "window.scrollTo(0, document.body.scrollHeight)",
            "up": "window.scrollBy(0, -500)",
            "down": "window.scrollBy(0, 500)",
        }

        try:
            command = scroll_map.get(direction.lower())
            if not command:
                raise ValueError("Invalid direction; use top, bottom, up, or down")
            async with self._lock:
                page = await self._ensure_page()
                await page.evaluate(command)
            return {"success": True, "message": f"Scrolled {direction}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def wait(self, duration_ms: int = 1000) -> Dict[str, Any]:
        """
        Wait for a duration in milliseconds.
        """

        try:
            if duration_ms < 0:
                raise ValueError("Duration must be non-negative")
            async with self._lock:
                page = await self._ensure_page()
                await page.wait_for_timeout(duration_ms)
            return {"success": True, "message": f"Waited {duration_ms}ms"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def screenshot(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Take a screenshot and return the saved path.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                self.screenshot_dir.mkdir(parents=True, exist_ok=True)
                label = sanitize_filename(name or "screenshot")
                filepath = self.screenshot_dir / f"{label}.png"
                await page.screenshot(path=str(filepath), full_page=True)
            return {
                "success": True,
                "message": f"Screenshot saved to {filepath}",
                "data": {"path": str(filepath)},
            }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def evaluate(self, script: str) -> Dict[str, Any]:
        """
        Evaluate JavaScript and return the result.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                result = await page.evaluate(script)
            return {"success": True, "message": "Evaluation complete", "data": {"result": result}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def get_url(self) -> Dict[str, Any]:
        """
        Return the current page URL.
        """

        async with self._lock:
            page = await self._ensure_page()
            return {"success": True, "message": "Current URL", "data": {"url": page.url}}

    async def upload(self, selector: str, file_path: str) -> Dict[str, Any]:
        """
        Upload a file to a file input.
        """

        try:
            validated = validate_path(file_path)
            async with self._lock:
                page = await self._ensure_page()
                await page.set_input_files(selector, str(validated), timeout=10000)
            return {"success": True, "message": f"Uploaded {validated}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def cookies(self) -> Dict[str, Any]:
        """
        Return cookies from the current context.
        """

        try:
            async with self._lock:
                if not self.context:
                    raise RuntimeError("No browser context available")
                cookies = await self.context.cookies()
            return {"success": True, "message": "Cookies retrieved", "data": {"cookies": cookies}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def storage(self) -> Dict[str, Any]:
        """
        Dump localStorage as JSON.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                storage = await page.evaluate("JSON.stringify(localStorage)")
            return {"success": True, "message": "Storage retrieved", "data": {"storage": storage}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def console(self) -> Dict[str, Any]:
        """
        Return collected console log entries.
        """

        try:
            async with self._lock:
                entries = list(self.console_log)
            return {"success": True, "message": "Console logs", "data": {"entries": entries}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def network(self) -> Dict[str, Any]:
        """
        Return collected network log entries.
        """

        try:
            async with self._lock:
                entries = list(self.network_log)
            return {"success": True, "message": "Network logs", "data": {"entries": entries}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    # ========== NEW TOOLS ==========

    async def wait_for(self, selector: str, timeout_ms: int = 10000) -> Dict[str, Any]:
        """
        Wait for an element matching selector to appear.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.wait_for_selector(selector, timeout=timeout_ms)
            return {"success": True, "message": f"Element {selector} appeared"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def wait_for_text(self, text: str, timeout_ms: int = 10000) -> Dict[str, Any]:
        """
        Wait for specific text to appear on the page.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.wait_for_selector(f"text={text}", timeout=timeout_ms)
            return {"success": True, "message": f"Text '{text}' appeared"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def text(self, selector: str) -> Dict[str, Any]:
        """
        Get the text content of an element.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                element = page.locator(selector).first
                content = await element.text_content()
            return {"success": True, "message": "Text retrieved", "data": {"text": content}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def value(self, selector: str) -> Dict[str, Any]:
        """
        Get the value of an input element.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                val = await page.input_value(selector, timeout=10000)
            return {"success": True, "message": "Value retrieved", "data": {"value": val}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def attr(self, selector: str, attribute: str) -> Dict[str, Any]:
        """
        Get an attribute value from an element.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                element = page.locator(selector).first
                val = await element.get_attribute(attribute)
            return {"success": True, "message": f"Attribute '{attribute}' retrieved", "data": {"value": val}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def count(self, selector: str) -> Dict[str, Any]:
        """
        Count elements matching the selector.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                num = await page.locator(selector).count()
            return {"success": True, "message": f"Found {num} elements", "data": {"count": num}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def press(self, key: str) -> Dict[str, Any]:
        """
        Press a keyboard key (e.g., Enter, Tab, Escape, ArrowDown).
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.keyboard.press(key)
            return {"success": True, "message": f"Pressed {key}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def reload(self) -> Dict[str, Any]:
        """
        Reload the current page.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.reload(wait_until="domcontentloaded")
            return {"success": True, "message": "Page reloaded"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def viewport(self, width: int, height: int) -> Dict[str, Any]:
        """
        Set the viewport size.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.set_viewport_size({"width": width, "height": height})
            return {"success": True, "message": f"Viewport set to {width}x{height}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def assert_visible(self, selector: str) -> Dict[str, Any]:
        """
        Assert that an element is visible. Returns pass/fail status.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                visible = await page.locator(selector).first.is_visible()
            if visible:
                return {"success": True, "message": f"[PASS] {selector} is visible", "data": {"visible": True}}
            return {"success": True, "message": f"[FAIL] {selector} is not visible", "data": {"visible": False}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def assert_text(self, selector: str, expected: str) -> Dict[str, Any]:
        """
        Assert that an element contains expected text. Returns pass/fail status.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                element = page.locator(selector).first
                content = await element.text_content() or ""
            if expected in content:
                return {"success": True, "message": f"[PASS] Found '{expected}' in {selector}", "data": {"found": True, "text": content}}
            return {"success": True, "message": f"[FAIL] '{expected}' not in {selector}", "data": {"found": False, "text": content}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def clear(self) -> Dict[str, Any]:
        """
        Clear localStorage and sessionStorage.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.evaluate("localStorage.clear(); sessionStorage.clear();")
            return {"success": True, "message": "Storage cleared"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def dialog(self, action: str, prompt_text: str = "") -> Dict[str, Any]:
        """
        Handle JavaScript dialogs (alert, confirm, prompt).
        Action: 'accept' or 'dismiss'. For prompts, provide prompt_text.
        """

        try:
            async def handle_dialog(dialog):
                if action == "accept":
                    await dialog.accept(prompt_text)
                else:
                    await dialog.dismiss()

            async with self._lock:
                page = await self._ensure_page()
                page.once("dialog", handle_dialog)
            return {"success": True, "message": f"Dialog handler set to {action}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def wait_for_url(self, pattern: str, timeout_ms: int = 10000) -> Dict[str, Any]:
        """
        Wait for the URL to contain the specified pattern.
        Useful for waiting after form submissions or navigation.
        """

        import re

        try:
            async with self._lock:
                page = await self._ensure_page()
                # Use regex to match pattern anywhere in URL
                await page.wait_for_url(re.compile(f".*{re.escape(pattern)}.*"), timeout=timeout_ms)
            return {"success": True, "message": f"URL now contains '{pattern}'", "data": {"url": page.url}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def assert_url(self, pattern: str) -> Dict[str, Any]:
        """
        Assert that the current URL contains the expected pattern. Returns pass/fail status.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                current_url = page.url
            if pattern in current_url:
                return {"success": True, "message": f"[PASS] URL contains '{pattern}'", "data": {"match": True, "url": current_url}}
            return {"success": True, "message": f"[FAIL] URL does not contain '{pattern}'", "data": {"match": False, "url": current_url}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def wait_for_load_state(self, state: str = "networkidle") -> Dict[str, Any]:
        """
        Wait for the page to reach a specific load state.
        States: 'load', 'domcontentloaded', 'networkidle'
        """

        valid_states = {"load", "domcontentloaded", "networkidle"}
        if state not in valid_states:
            return {"success": False, "message": f"Invalid state '{state}'. Use: {', '.join(valid_states)}"}

        try:
            async with self._lock:
                page = await self._ensure_page()
                # Type-safe cast after validation
                load_state: Any = state
                await page.wait_for_load_state(load_state)
            return {"success": True, "message": f"Page reached '{state}' state"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}


def main() -> None:
    """
    CLI entrypoint for running the MCP server.
    """

    parser = argparse.ArgumentParser(description="agent-browser MCP server")
    parser.add_argument("--visible", action="store_true", help="Run the browser headed")
    parser.add_argument("--allow-private", action="store_true", help="Allow navigation to private IP ranges")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    server = BrowserServer("agent-browser")
    # Configure but don't start - lazy init on first tool call
    server.configure(allow_private=args.allow_private, headless=not args.visible)
    server.server.run()


if __name__ == "__main__":
    main()
