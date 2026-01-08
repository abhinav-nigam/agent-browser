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

import aiohttp

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
        self._mocked_routes: List[str] = []
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

        # Agent utilities (call get_agent_guide first for full documentation)
        self.server.tool()(self.get_agent_guide)
        self.server.tool()(self.browser_status)
        self.server.tool()(self.check_local_port)
        self.server.tool()(self.page_state)
        self.server.tool()(self.find_elements)
        self.server.tool()(self.suggest_next_actions)
        self.server.tool()(self.validate_selector)

        # Perception tools (for reading page content)
        self.server.tool()(self.get_page_markdown)
        self.server.tool()(self.get_accessibility_tree)
        self.server.tool()(self.find_relative)

        # Advanced tools
        self.server.tool()(self.wait_for_change)
        self.server.tool()(self.highlight)
        self.server.tool()(self.mock_network)
        self.server.tool()(self.clear_mocks)

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

    async def _find_similar_elements(self, failed_selector: str, page: Page) -> List[Dict[str, str]]:
        """
        Find similar elements on the page when a selector fails.
        Returns a list of suggestions with selectors and text.
        """

        try:
            # Extract key terms from the failed selector for fuzzy matching
            search_terms: List[str] = []
            lower_selector = failed_selector.lower()

            # Extract text from text= selectors
            if "text=" in lower_selector:
                text_part = failed_selector.split("text=")[-1].strip("'\"")
                search_terms.append(text_part.lower())

            # Extract ID patterns
            if "#" in failed_selector:
                id_part = failed_selector.split("#")[-1].split()[0].split(".")[0]
                search_terms.append(id_part.lower())

            # Find visible interactive elements
            suggestions = await page.evaluate("""
                (searchTerms) => {
                    const suggestions = [];
                    const interactable = document.querySelectorAll(
                        'button, a, input, select, [role="button"], [onclick]'
                    );

                    for (const el of interactable) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;

                        const text = (el.textContent || '').trim().slice(0, 50);
                        const id = el.id || '';
                        const name = el.name || '';
                        const placeholder = el.placeholder || '';
                        const combined = (text + ' ' + id + ' ' + name + ' ' + placeholder).toLowerCase();

                        // Check if any search term matches
                        let score = 0;
                        for (const term of searchTerms) {
                            if (combined.includes(term)) score += 2;
                            // Partial matches - split by whitespace, hyphens, underscores
                            for (const word of term.split(/[\\s_-]+/)) {
                                if (word.length > 2 && combined.includes(word)) score += 1;
                            }
                        }

                        // Always include buttons and links with text
                        if (text && (el.tagName === 'BUTTON' || el.tagName === 'A')) {
                            score += 0.5;
                        }

                        if (score > 0 || suggestions.length < 5) {
                            let selector = '';
                            if (id) selector = '#' + id;
                            else if (text && text.length < 30) selector = `text="${text}"`;
                            else if (name) selector = `[name="${name}"]`;

                            if (selector) {
                                suggestions.push({
                                    selector: selector,
                                    text: text.slice(0, 40),
                                    tag: el.tagName.toLowerCase(),
                                    score: score
                                });
                            }
                        }

                        if (suggestions.length >= 10) break;
                    }

                    // Sort by score descending
                    suggestions.sort((a, b) => b.score - a.score);
                    return suggestions.slice(0, 5);
                }
            """, search_terms)

            return suggestions  # type: ignore
        except Exception:  # pylint: disable=broad-except
            return []

    def _build_selector_hint_message(
        self, original_error: str, suggestions: List[Dict[str, str]]
    ) -> str:
        """Build an error message with selector hints."""
        if not suggestions:
            return original_error

        hint_lines = [original_error, "", "Similar visible elements:"]
        for s in suggestions[:5]:
            hint_lines.append(f"  - {s['selector']} ({s['tag']}: \"{s['text']}\")")

        return "\n".join(hint_lines)

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
        [Agent Browser] Navigate to a URL. Validates URL for security (blocks private IPs by default).
        Waits for 'domcontentloaded' event. Use --allow-private flag to access localhost.
        Returns success/failure with the navigated URL.
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
        [Agent Browser] Click an element matching the selector.
        Supports Playwright selectors: css, text='...', xpath=..., :has-text().
        Auto-waits for element to be visible and actionable.
        On failure, returns suggestions for similar visible elements.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.click(selector, timeout=10000)
            return {"success": True, "message": f"Clicked {selector}"}
        except Exception as exc:  # pylint: disable=broad-except
            error_msg = str(exc)
            result: Dict[str, Any] = {"success": False, "message": error_msg}

            # Try to find similar elements for helpful hints
            try:
                async with self._lock:
                    if self.page:
                        suggestions = await self._find_similar_elements(selector, self.page)
                        if suggestions:
                            result["message"] = self._build_selector_hint_message(error_msg, suggestions)
                            result["suggestions"] = suggestions
            except Exception:  # pylint: disable=broad-except
                pass

            return result

    async def click_nth(self, selector: str, index: int) -> Dict[str, Any]:
        """
        [Agent Browser] Click the nth element matching a selector (0-indexed).
        Use when multiple elements match and you need a specific one (e.g., 2nd button).
        Prefer this over click() when you get 'strict mode violation' errors.
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
        [Agent Browser] Clear and fill a form field with the given value.
        Clears existing content before typing. Auto-waits for element.
        Use 'type' instead if you need to trigger key-by-key JS events.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.fill(selector, value, timeout=10000)
            return {"success": True, "message": f"Filled {selector}"}
        except Exception as exc:  # pylint: disable=broad-except
            error_msg = str(exc)
            result: Dict[str, Any] = {"success": False, "message": error_msg}

            # Try to find similar elements for helpful hints
            try:
                async with self._lock:
                    if self.page:
                        suggestions = await self._find_similar_elements(selector, self.page)
                        if suggestions:
                            result["message"] = self._build_selector_hint_message(error_msg, suggestions)
                            result["suggestions"] = suggestions
            except Exception:  # pylint: disable=broad-except
                pass

            return result

    async def type_text(self, selector: str, text: str) -> Dict[str, Any]:
        """
        [Agent Browser] Type text character by character with key events.
        Slower than 'fill' but triggers JS keydown/keyup handlers.
        Use for autocomplete, live search, or character-counting inputs.
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
        [Agent Browser] Select an option in a <select> dropdown by its value attribute.
        The value must match the 'value' attr of an <option>, not the visible text.
        Use page_state() or find_elements() to discover available option values.
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
        [Agent Browser] Hover the mouse over an element to trigger hover states.
        Use for dropdown menus, tooltips, or elements that appear on hover.
        Auto-waits for element to be visible.
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
        [Agent Browser] Set keyboard focus on an element without clicking.
        Use for form fields before typing, or to trigger focus-based JS events.
        Prefer fill() for inputs - it handles focus automatically.
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
        [Agent Browser] Navigate back in browser history (like clicking Back button).
        Waits for page load. Use get_url() after to verify the destination.
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
        [Agent Browser] Navigate forward in browser history (like clicking Forward button).
        Only works if you previously navigated back. Waits for page load.
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
        [Agent Browser] Scroll the page in a direction: 'up', 'down', 'top', 'bottom'.
        Use to reveal elements below the fold or trigger lazy-loading content.
        'up'/'down' scroll by 500px; 'top'/'bottom' go to page extremes.
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
        [Agent Browser] Hard wait for a duration in milliseconds.
        Avoid when possible - prefer wait_for, wait_for_text, or wait_for_url.
        Only use for animations or when no element change can be detected.
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
        [Agent Browser] Take a full-page screenshot (PNG).
        Returns the file path in data.path. Screenshots are saved to ./screenshots/.
        Use for visual verification or when you need to see the current page state.
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
        [Agent Browser] Execute JavaScript in the browser context and return the result.
        NOTE: This runs raw JS, NOT Playwright selectors. Use document.querySelector(), not text=.
        Useful for extracting data, checking state, or performing actions not covered by other tools.
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
        [Agent Browser] Get the current page URL.
        Returns {success: true, data: {url: '...'}}.
        """

        async with self._lock:
            page = await self._ensure_page()
            return {"success": True, "message": "Current URL", "data": {"url": page.url}}

    async def upload(self, selector: str, file_path: str) -> Dict[str, Any]:
        """
        [Agent Browser] Upload a file to an <input type="file"> element.
        file_path must be an absolute path to an existing file on the local system.
        Use for file upload forms, image uploads, document submissions.
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
        [Agent Browser] Get all cookies for the current browser context.
        Returns data.cookies array with name, value, domain, path, expires, etc.
        Use to verify authentication state or inspect session data.
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
        [Agent Browser] Get localStorage contents as JSON string.
        Returns data.storage. Use JSON.parse() on result to access individual keys.
        For sessionStorage, use evaluate('JSON.stringify(sessionStorage)').
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
        [Agent Browser] Get browser console log entries (errors, warnings, logs).
        Returns data.entries array with type, text, location. Max 200 entries retained.
        Use to debug JS errors or verify console.log output.
        """

        try:
            async with self._lock:
                entries = list(self.console_log)
            return {"success": True, "message": "Console logs", "data": {"entries": entries}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def network(self) -> Dict[str, Any]:
        """
        [Agent Browser] Get network request log (API calls, resource loads, failures).
        Returns data.entries array with method, url, status, failure. Max 200 entries.
        Use to verify API calls were made or debug failed requests.
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
        [Agent Browser] Wait for an element to appear in the DOM.
        Use after actions that load dynamic content. Most interaction tools auto-wait,
        so only use this for elements that appear asynchronously after page interactions.
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
        [Agent Browser] Wait for specific text to appear anywhere on the page.
        Use after actions that trigger dynamic content (e.g., "Loading complete", "Success").
        More reliable than wait() for async operations with known completion text.
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
        [Agent Browser] Get the text content of an element.
        Returns the first matching element's textContent. Useful for verification.
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
        [Agent Browser] Get the current value of an input, textarea, or select element.
        Use to verify form state or read user input. Returns data.value.
        For non-input elements, use text() instead.
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
        [Agent Browser] Get an HTML attribute value from an element.
        Common attributes: href, src, class, data-*, aria-*, disabled.
        Returns null if attribute doesn't exist. Use value() for input values.
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
        [Agent Browser] Count how many elements match a selector (includes hidden).
        Use to verify list lengths, check if elements exist, or before click_nth().
        Returns data.count. For detailed element info, use find_elements().
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
        [Agent Browser] Press a keyboard key globally (not tied to an element).
        Common keys: Enter, Tab, Escape, ArrowDown, ArrowUp, Backspace, Delete.
        Use after fill() to submit forms, or for keyboard navigation.
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
        [Agent Browser] Reload/refresh the current page (like pressing F5).
        Waits for DOM content to load. Use to reset page state or retry after errors.
        Clears form inputs but preserves cookies and localStorage.
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
        [Agent Browser] Resize the browser viewport to specific dimensions.
        Use to test responsive layouts. Common sizes: 1280x900 (desktop), 768x1024 (tablet), 375x667 (mobile).
        May trigger CSS media queries and responsive JS.
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
        [Agent Browser] Check if an element is visible (never throws).
        Returns {success: true, data: {visible: true/false}} with [PASS]/[FAIL] in message.
        Use for verification without breaking the flow on failure.
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
        [Agent Browser] Check if an element contains expected text (substring match).
        Returns [PASS]/[FAIL] in message - never throws. Use for verification without breaking flow.
        Returns data.found (bool) and truncated data.text (max 500 chars with context).
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                element = page.locator(selector).first
                content = await element.text_content() or ""

            if expected in content:
                # Found - show context around the match
                idx = content.find(expected)
                start = max(0, idx - 100)
                end = min(len(content), idx + len(expected) + 100)
                context = content[start:end]
                if start > 0:
                    context = "..." + context
                if end < len(content):
                    context = context + "..."

                return {
                    "success": True,
                    "message": f"[PASS] Found '{expected}' in {selector}",
                    "data": {"found": True, "text": context},
                }

            # Not found - show truncated content summary
            truncated = content[:500] + ("..." if len(content) > 500 else "")
            return {
                "success": True,
                "message": f"[FAIL] '{expected}' not found in {selector} ({len(content)} chars)",
                "data": {"found": False, "text": truncated, "total_length": len(content)},
            }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def clear(self) -> Dict[str, Any]:
        """
        [Agent Browser] Clear both localStorage and sessionStorage for the current origin.
        Use to reset app state, log out, or test fresh-user experience.
        Does NOT clear cookies - use browser restart for full reset.
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
        [Agent Browser] Set up handler for JavaScript dialogs (alert, confirm, prompt).
        Call BEFORE the action that triggers the dialog. Actions: 'accept' or 'dismiss'.
        For window.prompt(), provide prompt_text to enter a response.
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
        [Agent Browser] Wait for URL to contain a pattern (substring match).
        Use after form submissions, login flows, or redirects. E.g., wait_for_url('/dashboard').
        Returns data.url with the final URL.
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
        [Agent Browser] Check if current URL contains a pattern (substring match).
        Returns [PASS]/[FAIL] in message - never throws. Use for verification.
        Returns data.match (bool) and data.url (current URL).
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
        [Agent Browser] Wait for page to reach a load state: 'load', 'domcontentloaded', 'networkidle'.
        'networkidle' waits until no network requests for 500ms - good for SPAs.
        'domcontentloaded' is faster but may miss async content.
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

    # ========== AGENT UTILITY TOOLS ==========

    async def get_agent_guide(self, section: Optional[str] = None) -> Dict[str, Any]:
        """
        [Agent Browser] Get the AI agent quick reference guide.
        **CALL THIS FIRST** to understand how to use this browser automation tool effectively.
        Returns: selector syntax, tool categories, common patterns, and best practices.
        Optional: Pass section='selectors'|'tools'|'patterns'|'errors' for specific info.
        """

        guide_sections = {
            "intro": """# Agent Browser - AI Agent Quick Reference

## First Steps (Start Here!)

At the start of any browser automation session:
1. get_agent_guide()      # You're reading this - understand the tools
2. browser_status()       # Check capabilities, permissions, viewport
3. check_local_port(5000) # If testing local app, verify it's running
4. goto("http://...")     # Navigate to target
5. page_state()           # Get interactive elements with selectors""",

            "selectors": """## Selector Reference

All selectors use **Playwright's selector engine** - NOT standard document.querySelector().

| Type | Syntax | Example |
|------|--------|---------|
| CSS | selector | #login-btn, .nav-item, button |
| Text (exact) | text="..." | text="Sign In" |
| Text (partial) | text=... | text=Sign |
| Has text | tag:has-text("...") | button:has-text("Submit") |
| XPath | xpath=... | xpath=//button[@type="submit"] |
| Placeholder | placeholder=... | placeholder=Enter email |
| Nth match | selector >> nth=N | .item >> nth=0 (first) |
| Chained | parent >> child | #form >> button |

**Important:** :has-text() works in click/fill/wait_for - NOT in evaluate (raw JS).""",

            "tools": """## Tool Categories

### Navigation: goto, back, forward, reload, get_url
### Interactions: click, click_nth, fill, type, select, hover, focus, press
### Waiting: wait, wait_for, wait_for_text, wait_for_url, wait_for_load_state, wait_for_change
### Data: screenshot, text, value, attr, count, evaluate
### Assertions: assert_visible, assert_text, assert_url (return PASS/FAIL, never throw)
### Page State: scroll, viewport, cookies, storage, clear
### Debugging: console, network, dialog, highlight
### Agent Utils: get_agent_guide, browser_status, check_local_port, page_state, find_elements
### Perception: get_page_markdown, get_accessibility_tree, find_relative (for READING content)
### Testing: mock_network, clear_mocks (for mocking API calls)

**All interaction tools auto-wait** for elements to be visible and actionable.
You do NOT need wait_for before click or fill.""",

            "patterns": """## Common Patterns

### Fill form and submit:
fill("#email", "user@example.com")
fill("#password", "secret123")
click("button[type='submit']")
wait_for_url("/dashboard")

### Click by visible text:
click("text=Sign In")
click("button:has-text('Submit')")

### Wait for dynamic content:
click("#load-more")
wait_for_text("Results loaded")

### Read page content (KEY for perception):
get_page_markdown("#results")  # Extract content as markdown
find_relative("text=Total:", "right", "span")  # Find value next to label
get_accessibility_tree()  # Understand component structure

### Wait for SPA updates:
click("#calculate")
wait_for_change("#results")  # Wait for content to mutate
get_page_markdown("#results")  # Read updated content

### Debug selectors:
highlight("#submit-btn")  # Visual border for verification
screenshot("debug")
find_elements("button")  # See all matching elements""",

            "errors": """## Error Handling

| Error Pattern | Cause | Solution |
|---------------|-------|----------|
| "Timeout exceeded" | Element not found | Use wait_for, check selector |
| "strict mode violation" | Multiple matches | Use click_nth or more specific selector |
| "Private IP blocked" | Accessing localhost | Need --allow-private flag |
| "element not visible" | Hidden/off-screen | Scroll or check display state |

## Security Notes
- page_state() and find_elements() mask sensitive fields (password, token, key, ssn, cvv, pin)
- check_local_port() only allows localhost/127.0.0.1/::1 (SSRF protection)
- Private IPs blocked by default (use --allow-private for local testing)""",

            "safety": """## Tool Safety & Side Effects

Use this to decide how aggressive to be with self-correction loops.

### SAFE (Read-only, Idempotent) - Can retry freely:
- get_agent_guide, browser_status, check_local_port
- page_state, find_elements, validate_selector, suggest_next_actions
- get_page_markdown, get_accessibility_tree, find_relative
- text, value, attr, count, get_url, evaluate (when only reading values)
- screenshot, console, network, cookies, storage
- assert_visible, assert_text, assert_url
- wait, wait_for, wait_for_text, wait_for_url, wait_for_load_state, wait_for_change

### MUTATING (Changes page state) - Retry with caution:
- click, click_nth, fill, type, select, press, upload
- hover, focus, scroll, viewport
- dialog (accepts/dismisses alerts)
- goto, back, forward, reload
- clear (clears storage)
- highlight (temporary visual change)
- evaluate (when modifying DOM - use caution)

### EXTERNAL EFFECTS (May cost money/send data) - Confirm before retrying:
- click on buy/submit/send buttons
- fill in payment forms
- Any action after filling sensitive forms

### NETWORK MODIFICATION:
- mock_network (sets up interception - reversible with clear_mocks)
- clear_mocks (removes all mocks)

### Best Practices:
1. Use validate_selector() before click() to avoid blind failures
2. Use assert_* tools (return PASS/FAIL) instead of exceptions
3. Use page_state() to understand available elements before interacting
4. For SPAs, use wait_for_change() after clicking to detect updates"""
        }

        if section and section.lower() in guide_sections:
            content = guide_sections[section.lower()]
            return {
                "success": True,
                "message": f"Agent guide section: {section}",
                "data": {"section": section, "content": content}
            }

        # Return full guide
        full_guide = "\n\n".join([
            guide_sections["intro"],
            guide_sections["selectors"],
            guide_sections["tools"],
            guide_sections["safety"],
            guide_sections["patterns"],
            guide_sections["errors"]
        ])

        return {
            "success": True,
            "message": "Agent Browser quick reference guide",
            "data": {
                "content": full_guide,
                "sections_available": list(guide_sections.keys()),
                "tip": "Call get_agent_guide(section='selectors') for specific sections"
            }
        }

    async def browser_status(self) -> Dict[str, Any]:
        """
        [Agent Browser] Get browser capabilities and current state.
        Call this at the start of a session to understand available features.
        Returns: engine, mode, permissions, viewport, current URL, and readiness status.
        """

        try:
            permissions = ["public_internet"]
            if self.allow_private:
                permissions.append("localhost")
                permissions.append("private_networks")

            # Default values
            viewport: Dict[str, Any] = {"width": 1280, "height": 900}
            active_page = None

            # Get actual page info if browser is started (inside lock for thread safety)
            if self._started and self.page:
                async with self._lock:
                    if self.page:  # Re-check after acquiring lock
                        actual_viewport = self.page.viewport_size
                        if actual_viewport:
                            viewport = dict(actual_viewport)
                        active_page = {
                            "url": self.page.url,
                            "title": await self.page.title(),
                        }

            status_data: Dict[str, Any] = {
                "status": "ready" if self._started else "idle",
                "engine": "chromium",
                "mode": "mcp_server",
                "headless": self.headless,
                "permissions": permissions,
                "viewport": viewport,
                "screenshot_dir": str(self.screenshot_dir),
                "selector_engines": [
                    "css",
                    "xpath",
                    "text=",
                    "id=",
                    "placeholder=",
                    ":has-text()",
                    ">> nth=",
                ],
                "auto_wait": True,
                "default_timeout_ms": 10000,
                "active_page": active_page,
                # Capability flags for agents to branch logic
                "capabilities": {
                    "javascript": True,  # Always enabled in Playwright
                    "cookies": True,
                    "local_storage": True,
                    "file_upload": True,
                    "file_download": True,  # Playwright handles downloads in both modes
                    "clipboard": not self.headless,  # Clipboard access requires headed mode
                    "network_interception": True,  # mock_network is available
                    "console_access": True,  # console() tool available
                    "screenshots": True,
                    "pdf_generation": True,  # Playwright can generate PDFs
                },
                "active_mocks": len(self._mocked_routes),
            }

            return {
                "success": True,
                "message": "Browser status retrieved",
                "data": status_data,
            }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def check_local_port(self, port: int, host: str = "localhost") -> Dict[str, Any]:
        """
        [Agent Browser] Check if a local service is running and responding.
        Use this before attempting to navigate to local apps to verify they're up.
        Host is restricted to localhost/127.0.0.1 for security.
        Returns: port status, HTTP response code (if applicable), and service hints.
        """

        # Security: Only allow localhost probing to prevent SSRF
        allowed_hosts = {"localhost", "127.0.0.1", "::1"}
        if host.lower() not in allowed_hosts:
            return {
                "success": False,
                "message": f"Host '{host}' not allowed. Only localhost/127.0.0.1 permitted for security.",
                "data": {"port": port, "host": host, "reachable": False},
            }

        result: Dict[str, Any] = {
            "port": port,
            "host": host,
            "reachable": False,
            "http_status": None,
            "service_hint": None,
        }

        # Check TCP connectivity using async to avoid blocking the event loop
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            result["reachable"] = True
        except asyncio.TimeoutError:
            return {
                "success": True,
                "message": f"Port {port} connection timed out on {host}",
                "data": result,
            }
        except ConnectionRefusedError:
            return {
                "success": True,
                "message": f"Port {port} is not open on {host} (connection refused)",
                "data": result,
            }
        except OSError as exc:
            return {
                "success": False,
                "message": f"Could not check port {port}: {exc}",
                "data": result,
            }

        # Try HTTP request to get more info
        try:
            url = f"http://{host}:{port}/"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                async with session.get(url) as response:
                    result["http_status"] = response.status
                    # Try to detect service from response headers
                    server_header = response.headers.get("Server", "")
                    if server_header:
                        result["service_hint"] = server_header
                    # Check for common frameworks in HTML
                    if response.status == 200:
                        try:
                            body = await response.text()
                            if "<title>" in body.lower():
                                title_match = re.search(
                                    r"<title>(.*?)</title>", body, re.IGNORECASE
                                )
                                if title_match:
                                    result["page_title"] = title_match.group(1).strip()
                        except Exception:  # pylint: disable=broad-except
                            pass

            message = f"Port {port} is active (HTTP {result['http_status']})"
            if result.get("page_title"):
                message += f" - '{result['page_title']}'"

            # Add permission reminder
            if not self.allow_private:
                result["warning"] = (
                    "Private IP access is currently BLOCKED. "
                    "Restart server with --allow-private to navigate to this service."
                )
                message += ". NOTE: --allow-private flag required to navigate"

            return {
                "success": True,
                "message": message,
                "data": result,
            }
        except aiohttp.ClientError:
            # Port is open but not HTTP
            return {
                "success": True,
                "message": f"Port {port} is open but not responding to HTTP",
                "data": result,
            }
        except Exception as exc:  # pylint: disable=broad-except
            return {
                "success": True,
                "message": f"Port {port} is open (HTTP check failed: {exc})",
                "data": result,
            }

    async def page_state(self, include_text: bool = False) -> Dict[str, Any]:
        """
        [Agent Browser] Get comprehensive current page state snapshot.
        Returns: URL, title, viewport size, visible interactable elements, and form fields.
        Use this after actions to understand what changed without taking a screenshot.
        Set include_text=True to also get a text summary of the page content (headings, key text).
        """

        try:
            async with self._lock:
                page = await self._ensure_page()

                # Basic page info
                url = page.url
                title = await page.title()
                viewport = page.viewport_size or {"width": 1280, "height": 900}

                # Get visible interactive elements (limited to prevent huge responses)
                # Security: Mask password fields and truncate sensitive values
                interactables = await page.evaluate("""
                    () => {
                        const elements = [];
                        const selectors = [
                            'a[href]',
                            'button',
                            'input:not([type="hidden"])',
                            'select',
                            'textarea',
                            '[role="button"]',
                            '[onclick]',
                            '[tabindex]:not([tabindex="-1"])'
                        ];

                        // Sensitive input types that should have values masked
                        const sensitiveTypes = ['password', 'secret', 'token', 'key', 'credential', 'ssn', 'cvv', 'pin'];

                        for (const selector of selectors) {
                            for (const el of document.querySelectorAll(selector)) {
                                const rect = el.getBoundingClientRect();
                                // Skip hidden/off-screen elements
                                if (rect.width === 0 || rect.height === 0) continue;
                                if (rect.top > window.innerHeight || rect.bottom < 0) continue;

                                const inputType = (el.type || '').toLowerCase();
                                const inputName = (el.name || '').toLowerCase();
                                const inputId = (el.id || '').toLowerCase();

                                // Check if this is a sensitive field
                                const isSensitive = inputType === 'password' ||
                                    sensitiveTypes.some(t => inputName.includes(t) || inputId.includes(t));

                                // Mask value for sensitive fields
                                let value = null;
                                if (el.value) {
                                    if (isSensitive) {
                                        value = el.value.length > 0 ? '[MASKED]' : null;
                                    } else {
                                        // Truncate long values
                                        value = el.value.slice(0, 100);
                                    }
                                }

                                const info = {
                                    tag: el.tagName.toLowerCase(),
                                    type: el.type || null,
                                    text: (el.textContent || '').trim().slice(0, 50),
                                    id: el.id || null,
                                    name: el.name || null,
                                    placeholder: el.placeholder || null,
                                    value: value,
                                    href: el.href ? el.href.slice(0, 200) : null  // Truncate long URLs
                                };

                                // Generate a suggested selector
                                if (el.id) {
                                    info.selector = '#' + el.id;
                                } else if (el.name) {
                                    info.selector = `[name="${el.name}"]`;
                                } else if (info.text && info.text.length > 0 && info.text.length < 30) {
                                    info.selector = `text="${info.text}"`;
                                } else if (el.placeholder) {
                                    info.selector = `[placeholder="${el.placeholder}"]`;
                                }

                                elements.push(info);
                                if (elements.length >= 30) break;  // Limit output
                            }
                            if (elements.length >= 30) break;
                        }
                        return elements;
                    }
                """)

                # Get form count
                form_count = await page.locator("form").count()

                # Build response data
                data: Dict[str, Any] = {
                    "url": url,
                    "title": title,
                    "viewport": viewport,
                    "form_count": form_count,
                    "interactive_elements": interactables,
                    "element_count": len(interactables),
                }

                # Optionally include text summary
                if include_text:
                    text_summary = await page.evaluate("""
                        () => {
                            const summary = { headings: [], key_text: [] };

                            // Extract headings (h1-h3)
                            for (const h of document.querySelectorAll('h1, h2, h3')) {
                                const text = h.textContent.trim();
                                if (text && text.length < 100) {
                                    summary.headings.push({
                                        level: parseInt(h.tagName[1]),
                                        text: text
                                    });
                                }
                                if (summary.headings.length >= 10) break;
                            }

                            // Extract key text content (paragraphs, main content)
                            const mainContent = document.querySelector('main, article, [role="main"], .content, #content')
                                || document.body;

                            // Get visible text blocks
                            const textBlocks = [];
                            const walker = document.createTreeWalker(
                                mainContent,
                                NodeFilter.SHOW_TEXT,
                                {
                                    acceptNode: (node) => {
                                        const parent = node.parentElement;
                                        if (!parent) return NodeFilter.FILTER_REJECT;
                                        const tag = parent.tagName.toLowerCase();
                                        if (['script', 'style', 'noscript'].includes(tag)) {
                                            return NodeFilter.FILTER_REJECT;
                                        }
                                        const text = node.textContent.trim();
                                        if (text.length < 10) return NodeFilter.FILTER_REJECT;
                                        return NodeFilter.FILTER_ACCEPT;
                                    }
                                }
                            );

                            let charCount = 0;
                            const maxChars = 1000;
                            while (walker.nextNode() && charCount < maxChars) {
                                const text = walker.currentNode.textContent.trim();
                                if (text.length > 10) {
                                    const truncated = text.slice(0, maxChars - charCount);
                                    summary.key_text.push(truncated);
                                    charCount += truncated.length;
                                }
                            }

                            return summary;
                        }
                    """)
                    data["text_summary"] = text_summary

                return {
                    "success": True,
                    "message": f"Page state: {title or url}",
                    "data": data,
                }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def find_elements(self, selector: str, include_hidden: bool = False) -> Dict[str, Any]:
        """
        [Agent Browser] Find elements matching a selector and return details about each.
        Useful for debugging selector issues or understanding page structure.
        Returns: count, and details about each matching element (max 20).
        When include_hidden=False, only visible elements are counted and returned.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                locator = page.locator(selector)
                total_count = await locator.count()

                elements: List[Dict[str, Any]] = []
                visible_count = 0
                hidden_count = 0

                for i in range(total_count):
                    el = locator.nth(i)
                    try:
                        is_visible = await el.is_visible()

                        if is_visible:
                            visible_count += 1
                        else:
                            hidden_count += 1
                            if not include_hidden:
                                continue

                        # Limit to 20 elements in output
                        if len(elements) >= 20:
                            continue

                        el_info: Dict[str, Any] = {
                            "index": i,
                            "visible": is_visible,
                            "enabled": await el.is_enabled(),
                            "text": ((await el.text_content()) or "").strip()[:100],
                        }

                        # Try to get common attributes (mask sensitive values)
                        for attr in ["id", "name", "class", "type", "href", "placeholder"]:
                            try:
                                val = await el.get_attribute(attr)
                                if val:
                                    el_info[attr] = val[:100] if len(val) > 100 else val
                            except Exception:  # pylint: disable=broad-except
                                pass

                        # Handle value separately - mask sensitive fields
                        # Must match the same patterns as page_state for consistency
                        try:
                            val = await el.get_attribute("value")
                            if val:
                                input_type = (el_info.get("type") or "").lower()
                                input_name = (el_info.get("name") or "").lower()
                                input_id = (el_info.get("id") or "").lower()
                                sensitive_patterns = ["password", "secret", "token", "key", "credential", "ssn", "cvv", "pin"]
                                is_sensitive = (
                                    input_type == "password" or
                                    any(p in input_name for p in sensitive_patterns) or
                                    any(p in input_id for p in sensitive_patterns)
                                )
                                el_info["value"] = "[MASKED]" if is_sensitive else val[:100]
                        except Exception:  # pylint: disable=broad-except
                            pass

                        # Get bounding box
                        try:
                            bbox = await el.bounding_box()
                            if bbox:
                                el_info["position"] = {
                                    "x": round(bbox["x"]),
                                    "y": round(bbox["y"]),
                                    "width": round(bbox["width"]),
                                    "height": round(bbox["height"]),
                                }
                        except Exception:  # pylint: disable=broad-except
                            pass

                        elements.append(el_info)
                    except Exception:  # pylint: disable=broad-except
                        continue

                # Build accurate message based on what's being returned
                if include_hidden:
                    reported_count = total_count
                    message = f"Found {total_count} element(s) matching '{selector}'"
                    if hidden_count > 0:
                        message += f" ({visible_count} visible, {hidden_count} hidden)"
                else:
                    reported_count = visible_count
                    message = f"Found {visible_count} visible element(s) matching '{selector}'"
                    if hidden_count > 0:
                        message += f" ({hidden_count} more hidden)"

                if len(elements) < reported_count:
                    message += f" (showing {len(elements)})"

                return {
                    "success": True,
                    "message": message,
                    "data": {
                        "selector": selector,
                        "total_count": total_count,
                        "visible_count": visible_count,
                        "hidden_count": hidden_count,
                        "returned_count": len(elements),
                        "elements": elements,
                    },
                }
        except Exception as exc:  # pylint: disable=broad-except
            # Provide helpful hints for selector failures
            error_msg = str(exc)
            hints: List[str] = []

            if "Timeout" in error_msg:
                hints.append("Element may not exist or may be hidden")
                hints.append("Try wait_for(selector) first or check selector syntax")
            if "strict mode violation" in error_msg.lower():
                hints.append("Multiple elements match. Use click_nth or more specific selector")

            result: Dict[str, Any] = {"success": False, "message": error_msg}
            if hints:
                result["hints"] = hints
            return result

    async def suggest_next_actions(self) -> Dict[str, Any]:
        """
        [Agent Browser] Analyze current page and suggest relevant tools/actions.
        Use when stuck or unsure what to do next. Returns context-aware hints based on:
        - Page type (PDF, canvas, iframes)
        - Forms, modals, error messages
        - Loading states and dynamic content
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                url = page.url

                suggestions: List[Dict[str, Any]] = []
                warnings: List[str] = []

                # Analyze page context
                analysis = await page.evaluate("""
                    () => {
                        const result = {
                            hasForm: document.querySelectorAll('form').length > 0,
                            formInputs: document.querySelectorAll('input, textarea, select').length,
                            hasButtons: document.querySelectorAll('button, [type="submit"], [role="button"]').length,
                            hasLinks: document.querySelectorAll('a[href]').length,
                            hasLoadingIndicator: !!(
                                document.querySelector('[class*="loading"]') ||
                                document.querySelector('[class*="spinner"]') ||
                                document.querySelector('[aria-busy="true"]')
                            ),
                            hasErrorMessage: !!(
                                document.querySelector('[class*="error"]') ||
                                document.querySelector('[role="alert"]') ||
                                document.querySelector('.alert-danger')
                            ),
                            hasModal: !!(
                                document.querySelector('[role="dialog"]') ||
                                document.querySelector('.modal.show') ||
                                document.querySelector('[aria-modal="true"]')
                            ),
                            hasTable: document.querySelectorAll('table').length > 0,
                            hasIframe: document.querySelectorAll('iframe').length > 0,
                            hasCanvas: document.querySelectorAll('canvas').length > 0,
                            bodyText: document.body?.innerText?.slice(0, 500) || '',
                            title: document.title,
                        };
                        return result;
                    }
                """)

                # Check for PDF
                if url.lower().endswith('.pdf') or 'application/pdf' in url:
                    warnings.append("PDF detected - DOM selectors won't work on PDF content")
                    suggestions.append({
                        "action": "screenshot",
                        "reason": "Capture PDF visually for analysis",
                        "priority": "high",
                    })

                # Check for loading state
                if analysis.get("hasLoadingIndicator"):
                    suggestions.append({
                        "action": "wait_for_change or wait_for_text",
                        "reason": "Page appears to be loading - wait for content to stabilize",
                        "priority": "high",
                    })

                # Check for error messages
                if analysis.get("hasErrorMessage"):
                    suggestions.append({
                        "action": "get_page_markdown or screenshot",
                        "reason": "Error message detected - read the error content",
                        "priority": "high",
                    })
                    suggestions.append({
                        "action": "console()",
                        "reason": "Check console for JavaScript errors",
                        "priority": "medium",
                    })

                # Check for modal/dialog
                if analysis.get("hasModal"):
                    suggestions.append({
                        "action": "page_state() then interact with modal",
                        "reason": "Modal dialog is open - interact with it first",
                        "priority": "high",
                    })

                # Check for forms
                if analysis.get("hasForm") and analysis.get("formInputs", 0) > 0:
                    suggestions.append({
                        "action": "page_state() to see form fields",
                        "reason": f"Form with {analysis['formInputs']} input(s) detected",
                        "priority": "medium",
                    })

                # Check for canvas (games, charts)
                if analysis.get("hasCanvas"):
                    warnings.append("Canvas element detected - text extraction won't work, use screenshot")
                    suggestions.append({
                        "action": "screenshot",
                        "reason": "Canvas content requires visual inspection",
                        "priority": "medium",
                    })

                # Check for iframes
                if analysis.get("hasIframe"):
                    warnings.append("Iframe detected - content inside iframe may not be accessible with standard selectors")

                # Check for tables (data extraction)
                if analysis.get("hasTable"):
                    suggestions.append({
                        "action": "get_page_markdown",
                        "reason": "Table detected - extract structured data",
                        "priority": "medium",
                    })

                # Default suggestions if page looks normal
                if not suggestions:
                    if analysis.get("hasButtons", 0) > 0 or analysis.get("hasLinks", 0) > 0:
                        suggestions.append({
                            "action": "page_state()",
                            "reason": "Get interactive elements with ready-to-use selectors",
                            "priority": "medium",
                        })
                    suggestions.append({
                        "action": "get_page_markdown()",
                        "reason": "Read page content as structured text",
                        "priority": "medium",
                    })

                return {
                    "success": True,
                    "message": f"Analyzed page: {analysis.get('title', 'Untitled')[:50]}",
                    "data": {
                        "url": url,
                        "suggestions": suggestions,
                        "warnings": warnings,
                        "page_context": {
                            "has_form": analysis.get("hasForm"),
                            "has_loading": analysis.get("hasLoadingIndicator"),
                            "has_error": analysis.get("hasErrorMessage"),
                            "has_modal": analysis.get("hasModal"),
                            "has_table": analysis.get("hasTable"),
                            "has_canvas": analysis.get("hasCanvas"),
                            "interactive_elements": analysis.get("hasButtons", 0) + analysis.get("hasLinks", 0),
                        },
                    },
                }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def validate_selector(self, selector: str) -> Dict[str, Any]:
        """
        [Agent Browser] Validate a selector before using it in an action.
        Use to check if a selector matches elements and how many, preventing blind failures.
        Returns match count, sample text, and suggestions for ambiguous selectors.
        Lightweight alternative to find_elements for quick validation.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                locator = page.locator(selector)
                count = await locator.count()

                if count == 0:
                    # Try to provide helpful suggestions
                    suggestions: List[str] = []

                    # Check if it might be a timing issue
                    suggestions.append("Element may not exist yet - try wait_for(selector) first")

                    # Check for common selector mistakes
                    if selector.startswith("#") and " " in selector:
                        suggestions.append("ID selectors can't contain spaces - check for typos")
                    if selector.startswith("text=") and " " in selector and '"' not in selector:
                        suggestions.append("For text with spaces, use quotes: text=\"Sign In\" (exact) or just text=Sign (partial)")

                    return {
                        "success": True,
                        "message": f"No elements match '{selector}'",
                        "data": {
                            "valid": False,
                            "count": 0,
                            "suggestions": suggestions,
                        },
                    }

                # Get sample from first element
                first = locator.first
                sample_text = ""
                sample_tag = ""
                try:
                    sample_text = ((await first.text_content()) or "").strip()[:100]
                    sample_tag = await first.evaluate("el => el.tagName.toLowerCase()")
                except Exception:  # pylint: disable=broad-except
                    pass

                result_data: Dict[str, Any] = {
                    "valid": True,
                    "count": count,
                    "sample_tag": sample_tag,
                    "sample_text": sample_text,
                }

                # Provide guidance for multiple matches
                if count > 1:
                    result_data["note"] = f"Multiple matches ({count}) - use click_nth(selector, index) or refine selector"
                    result_data["suggested_selectors"] = [
                        f"{selector} >> nth=0",
                        f"{selector} >> nth={count-1}",
                    ]

                # Build descriptive message
                if sample_tag and sample_text:
                    preview = f"<{sample_tag}>{sample_text[:30]}{'...' if len(sample_text) > 30 else ''}</{sample_tag}>"
                elif sample_tag:
                    preview = f"<{sample_tag}> (empty)"
                else:
                    preview = "(element)"

                return {
                    "success": True,
                    "message": f"Selector matches {count} element(s): {preview}",
                    "data": result_data,
                }
        except Exception as exc:  # pylint: disable=broad-except
            return {
                "success": False,
                "message": f"Invalid selector: {exc}",
                "data": {"valid": False, "error": str(exc)},
            }

    # ========== PERCEPTION TOOLS ==========

    async def get_page_markdown(self, selector: Optional[str] = None, max_length: int = 8000) -> Dict[str, Any]:
        """
        [Agent Browser] Get page content as a structured markdown-like text.
        Use this to READ page content (articles, results, dashboards) - not just interactive elements.
        Returns headings, paragraphs, lists, and data in a clean hierarchical format.
        Optional selector to focus on a specific section (CSS selector only, e.g. '#results', '.content').
        max_length limits output size.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()

                # JavaScript to extract page content as markdown-like structure
                content = await page.evaluate("""
                    (args) => {
                        const { selector, maxLength } = args;
                        const root = selector ? document.querySelector(selector) : document.body;
                        if (!root) return { error: 'Selector not found' };

                        const lines = [];
                        let totalLength = 0;

                        function addLine(text, prefix = '') {
                            if (totalLength >= maxLength) return false;
                            const line = prefix + text.trim();
                            if (line) {
                                lines.push(line);
                                totalLength += line.length + 1;
                            }
                            return true;
                        }

                        // Track elements we've fully processed to avoid duplicates
                        const processed = new WeakSet();

                        function processNode(node, depth = 0) {
                            if (totalLength >= maxLength || depth > 50) return;

                            // Skip already processed
                            if (processed.has(node)) return;

                            if (node.nodeType === Node.TEXT_NODE) {
                                // Skip if parent was fully processed (handles text)
                                if (processed.has(node.parentNode)) return;
                                const text = node.textContent.trim();
                                if (text && text.length > 1) addLine(text);
                                return;
                            }
                            if (node.nodeType !== Node.ELEMENT_NODE) return;

                            const el = node;
                            const tag = el.tagName.toLowerCase();

                            // Skip script, style, svg, etc.
                            if (['script', 'style', 'svg', 'noscript', 'iframe'].includes(tag)) return;

                            // Check visibility (expensive, do after cheap checks)
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') return;

                            // Handle headings - mark as processed, don't recurse
                            if (/^h[1-6]$/.test(tag)) {
                                const level = parseInt(tag[1]);
                                const text = el.textContent.trim();
                                if (text) addLine(text, '#'.repeat(level) + ' ');
                                processed.add(el);
                                return;
                            }

                            // Handle lists - mark as processed, don't recurse
                            if (tag === 'li') {
                                const text = el.textContent.trim();
                                if (text) addLine(text.slice(0, 200), '- ');
                                processed.add(el);
                                return;
                            }

                            // Handle table rows - mark as processed, don't recurse
                            if (tag === 'tr') {
                                const cells = Array.from(el.querySelectorAll('th, td'))
                                    .map(c => c.textContent.trim().slice(0, 50))
                                    .filter(t => t);
                                if (cells.length) addLine(cells.join(' | '), '| ');
                                processed.add(el);
                                return;
                            }

                            // Handle pre/code blocks - preserve whitespace
                            if (tag === 'pre' || tag === 'code') {
                                const text = el.textContent.trim();
                                if (text) {
                                    addLine('```');
                                    addLine(text.slice(0, 500));
                                    addLine('```');
                                }
                                processed.add(el);
                                return;
                            }

                            // Recurse into children (don't extract direct text to avoid duplication)
                            for (const child of el.childNodes) {
                                processNode(child, depth + 1);
                            }
                        }

                        processNode(root);

                        return {
                            content: lines.join('\\n'),
                            lineCount: lines.length,
                            truncated: totalLength >= maxLength
                        };
                    }
                """, {"selector": selector, "maxLength": max_length})

                if content.get("error"):
                    return {"success": False, "message": content["error"]}

                return {
                    "success": True,
                    "message": f"Extracted {content['lineCount']} lines" + (" (truncated)" if content['truncated'] else ""),
                    "data": content,
                }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def get_accessibility_tree(self, selector: Optional[str] = None, max_length: int = 8000) -> Dict[str, Any]:
        """
        [Agent Browser] Get the accessibility tree for the page or a specific element.
        Cleaner than DOM for understanding form structures and component purposes.
        Returns roles, names, values in a YAML-like hierarchical format.
        Optional selector to focus on a specific element.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()

                # Use locator.aria_snapshot() - the modern Playwright API
                if selector:
                    locator = page.locator(selector).first
                    count = await page.locator(selector).count()
                    if count == 0:
                        return {"success": False, "message": f"Element not found: {selector}"}
                else:
                    locator = page.locator("body")

                snapshot = await locator.aria_snapshot()

                if not snapshot:
                    return {
                        "success": True,
                        "message": "No accessibility tree available (page may be empty)",
                        "data": {"tree": None},
                    }

                # Truncate if too long
                if len(snapshot) > max_length:
                    snapshot = snapshot[:max_length] + "\n... (truncated)"

                return {
                    "success": True,
                    "message": "Accessibility tree retrieved",
                    "data": {"tree": snapshot},
                }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def find_relative(
        self,
        anchor: str,
        direction: str,
        target: Optional[str] = None,
        max_distance: int = 500,
    ) -> Dict[str, Any]:
        """
        [Agent Browser] Find an element spatially relative to an anchor element.
        Directions: 'above', 'below', 'left', 'right', 'nearest'.
        Use for finding data near labels (e.g., value below "Total Gain" label).
        Returns the closest matching element in that direction.

        Note: 'anchor' uses Playwright selectors (text=, css, xpath).
              'target' can be:
                - CSS selector (div, .class, #id)
                - 'text' - find nearest element with direct text content (recommended for values)
                - None/omitted - searches all elements (may find containers)
        """

        valid_directions = {"above", "below", "left", "right", "nearest"}
        if direction.lower() not in valid_directions:
            return {
                "success": False,
                "message": f"Invalid direction '{direction}'. Use: {', '.join(valid_directions)}",
            }

        try:
            async with self._lock:
                page = await self._ensure_page()

                # Check anchor exists first (fast fail instead of 30s timeout)
                anchor_locator = page.locator(anchor)
                anchor_count = await anchor_locator.count()
                if anchor_count == 0:
                    return {"success": False, "message": f"Anchor element not found: {anchor}"}

                # Get anchor element's bounding box
                anchor_el = anchor_locator.first
                anchor_box = await anchor_el.bounding_box()
                if not anchor_box:
                    return {"success": False, "message": f"Anchor element not visible: {anchor}"}

                anchor_center = {
                    "x": anchor_box["x"] + anchor_box["width"] / 2,
                    "y": anchor_box["y"] + anchor_box["height"] / 2,
                }

                # Handle special "text" mode vs CSS selector
                text_mode = target and target.lower() == "text"
                target_selector = "*" if (not target or text_mode) else target

                result = await page.evaluate("""
                    (args) => {
                        const { anchorBox, anchorCenter, direction, targetSelector, maxDistance, textMode } = args;

                        // Helper: Check if element has direct text content (not just child text)
                        function hasDirectText(el) {
                            for (const node of el.childNodes) {
                                if (node.nodeType === Node.TEXT_NODE) {
                                    const text = node.textContent.trim();
                                    if (text.length > 0) return true;
                                }
                            }
                            return false;
                        }

                        // Helper: Check if element is a "leaf" text node (has text, minimal nested elements)
                        function isLeafText(el) {
                            const text = (el.textContent || '').trim();
                            if (!text) return false;

                            // Check direct text content
                            if (hasDirectText(el)) return true;

                            // Or element with single text-bearing child
                            const children = Array.from(el.children).filter(c => {
                                const style = window.getComputedStyle(c);
                                return style.display !== 'none' && c.textContent.trim();
                            });
                            return children.length <= 1 && text.length < 100;
                        }

                        // Get all potential target elements
                        const candidates = document.querySelectorAll(targetSelector);
                        let best = null;
                        let bestDistance = Infinity;
                        let bestScore = Infinity;

                        for (const el of candidates) {
                            // Skip script/style/hidden elements
                            const tag = el.tagName.toLowerCase();
                            if (['script', 'style', 'noscript', 'meta', 'link'].includes(tag)) continue;

                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;

                            // In text mode, only consider leaf text elements
                            if (textMode && !isLeafText(el)) continue;

                            const text = (el.textContent || '').trim().slice(0, 200);

                            // Skip empty elements
                            if (!text && !el.value) continue;

                            const center = {
                                x: rect.x + rect.width / 2,
                                y: rect.y + rect.height / 2
                            };

                            // Skip the anchor itself
                            if (Math.abs(center.x - anchorCenter.x) < 5 &&
                                Math.abs(center.y - anchorCenter.y) < 5) continue;

                            const dx = center.x - anchorCenter.x;
                            const dy = center.y - anchorCenter.y;
                            const distance = Math.sqrt(dx * dx + dy * dy);

                            if (distance > maxDistance) continue;

                            let isValid = false;
                            let score = distance;

                            switch (direction) {
                                case 'below':
                                    isValid = dy > 10 && Math.abs(dx) < rect.width + anchorBox.width;
                                    score = dy + Math.abs(dx) * 0.5;
                                    break;
                                case 'above':
                                    isValid = dy < -10 && Math.abs(dx) < rect.width + anchorBox.width;
                                    score = -dy + Math.abs(dx) * 0.5;
                                    break;
                                case 'right':
                                    isValid = dx > 10 && Math.abs(dy) < rect.height + anchorBox.height;
                                    score = dx + Math.abs(dy) * 0.5;
                                    break;
                                case 'left':
                                    isValid = dx < -10 && Math.abs(dy) < rect.height + anchorBox.height;
                                    score = -dx + Math.abs(dy) * 0.5;
                                    break;
                                case 'nearest':
                                    isValid = true;
                                    score = distance;
                                    break;
                            }

                            if (isValid && score < bestScore) {
                                bestScore = score;
                                bestDistance = distance;
                                best = {
                                    tag: tag,
                                    text: text,
                                    id: el.id || null,
                                    className: el.className || null,
                                    value: el.value || null,
                                    distance: Math.round(distance),
                                    position: { x: Math.round(rect.x), y: Math.round(rect.y) }
                                };

                                // Generate selector
                                if (el.id) {
                                    best.selector = '#' + el.id;
                                } else if (text && text.length < 30 && !text.includes('\\n')) {
                                    best.selector = `text="${text}"`;
                                } else if (el.name) {
                                    best.selector = `[name="${el.name}"]`;
                                }
                            }
                        }

                        return best;
                    }
                """, {
                    "anchorBox": anchor_box,
                    "anchorCenter": anchor_center,
                    "direction": direction.lower(),
                    "targetSelector": target_selector,
                    "maxDistance": max_distance,
                    "textMode": text_mode,
                })

                if not result:
                    return {
                        "success": True,
                        "message": f"No element found {direction} of anchor within {max_distance}px",
                        "data": {"found": False},
                    }

                return {
                    "success": True,
                    "message": f"Found {result['tag']} {direction} of anchor ({result['distance']}px away)",
                    "data": {"found": True, "element": result},
                }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    # ========== ADVANCED TOOLS ==========

    async def wait_for_change(
        self,
        selector: str,
        attribute: Optional[str] = None,
        timeout_ms: int = 10000,
    ) -> Dict[str, Any]:
        """
        [Agent Browser] Wait for an element's content or attribute to change.
        Use for SPAs that update DOM without navigation (loading states, live data).
        If attribute is None, watches for text content changes.
        """

        try:
            # Get initial state (with lock)
            async with self._lock:
                page = await self._ensure_page()
                locator = page.locator(selector).first

                if attribute:
                    initial_value = await locator.get_attribute(attribute)
                else:
                    initial_value = await locator.text_content()

            # Poll for changes (WITHOUT holding lock - allows other tools to run)
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            poll_interval = 0.1  # 100ms

            while True:
                elapsed = (loop.time() - start_time) * 1000
                if elapsed >= timeout_ms:
                    return {
                        "success": True,
                        "message": f"No change detected within {timeout_ms}ms",
                        "data": {"changed": False, "value": initial_value[:200] if initial_value is not None else None},
                    }

                await asyncio.sleep(poll_interval)

                # Re-acquire lock briefly to check value
                async with self._lock:
                    if attribute:
                        current_value = await locator.get_attribute(attribute)
                    else:
                        current_value = await locator.text_content()

                if current_value != initial_value:
                    return {
                        "success": True,
                        "message": f"Change detected after {int(elapsed)}ms",
                        "data": {
                            "changed": True,
                            "old_value": initial_value[:200] if initial_value is not None else None,
                            "new_value": current_value[:200] if current_value is not None else None,
                        },
                    }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def highlight(self, selector: str, color: str = "red", duration_ms: int = 2000) -> Dict[str, Any]:
        """
        [Agent Browser] Highlight an element with a colored border for visual debugging.
        Use before screenshot() to confirm you're targeting the correct element.
        Color can be any CSS color (red, blue, #ff0000, rgb(255,0,0), etc.). Duration in ms.
        """

        # Sanitize color to prevent CSS injection
        # Allow alphanumeric, #, -, _, (), commas, spaces, %, and . for CSS colors (rgba/hsla need decimals)
        safe_color = "".join(c for c in color if c.isalnum() or c in "#-_(), %.:")[:50]

        try:
            async with self._lock:
                page = await self._ensure_page()
                locator = page.locator(selector)
                count = await locator.count()

                if count == 0:
                    return {"success": False, "message": f"No elements found matching: {selector}"}

                # Apply highlight to each element using Playwright's locator
                for i in range(min(count, 20)):  # Limit to 20 elements
                    element = locator.nth(i)
                    await element.evaluate("""
                        (el, args) => {
                            const { color, duration } = args;
                            const originalOutline = el.style.outline;
                            const originalOutlineOffset = el.style.outlineOffset;

                            el.style.outline = `3px solid ${color}`;
                            el.style.outlineOffset = '2px';

                            setTimeout(() => {
                                el.style.outline = originalOutline || '';
                                el.style.outlineOffset = originalOutlineOffset || '';
                            }, duration);
                        }
                    """, {"color": safe_color, "duration": duration_ms})

                return {
                    "success": True,
                    "message": f"Highlighted {count} element(s) with {safe_color} border for {duration_ms}ms",
                    "data": {"count": count, "color": safe_color},
                }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def mock_network(
        self,
        url_pattern: str,
        response_body: str,
        status: int = 200,
        content_type: str = "application/json",
    ) -> Dict[str, Any]:
        """
        [Agent Browser] Mock network requests matching a URL pattern.
        Use for frontend isolation testing by intercepting and mocking API calls.
        Pattern uses glob matching (e.g., '**/api/users*'). Response body is returned as-is.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()

                # Create route handler
                async def handle_route(route):
                    await route.fulfill(
                        status=status,
                        content_type=content_type,
                        body=response_body,
                    )

                await page.route(url_pattern, handle_route)

                # Track mocked routes for clear_mocks
                self._mocked_routes.append(url_pattern)

                return {
                    "success": True,
                    "message": f"Mocking requests to '{url_pattern}' with status {status}",
                    "data": {
                        "pattern": url_pattern,
                        "status": status,
                        "content_type": content_type,
                        "response_preview": response_body[:100] + ("..." if len(response_body) > 100 else ""),
                    },
                }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": str(exc)}

    async def clear_mocks(self) -> Dict[str, Any]:
        """
        [Agent Browser] Clear all network mocks set by mock_network().
        Call this to restore normal network behavior after testing.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()

                for pattern in self._mocked_routes:
                    try:
                        await page.unroute(pattern)
                    except Exception:  # pylint: disable=broad-except
                        pass

                count = len(self._mocked_routes)
                self._mocked_routes.clear()

                return {
                    "success": True,
                    "message": f"Cleared {count} network mock(s)",
                    "data": {"cleared_count": count},
                }
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
