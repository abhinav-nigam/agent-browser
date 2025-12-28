"""
MCP Server for agent-browser.

Implements the Model Context Protocol to expose browser automation as tools.
Uses Playwright async API for low-latency, in-process control.
"""

import asyncio
import base64
import ipaddress
import json
import logging
import os
import socket
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Error as PlaywrightError

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

BLOCKED_SCHEMES = {
    'file', 'data', 'javascript', 'chrome', 'chrome-extension', 
    'about', 'view-source', 'ws', 'wss', 'ftp', 'blob', 'vbscript',
    'mailto', 'tel', 'gopher', 'vnc'
}

BLOCKED_HOSTS = {
    'localhost', '127.0.0.1', '::1', '0.0.0.0', 
    'metadata.google.internal', # GCP metadata
    '169.254.169.254', # AWS/GCP/Azure metadata
    'local', 'internal', 'localdomain'
}

PRIVATE_IP_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
    ipaddress.ip_network('100.64.0.0/10'), # CGNAT
]

# =============================================================================
# DATA MODELS
# =============================================================================

class BrowserErrorCode(str, Enum):
    SELECTOR_NOT_FOUND = "selector_not_found"
    NAVIGATION_TIMEOUT = "navigation_timeout"
    DIALOG_BLOCKING = "dialog_blocking"
    BROWSER_CRASHED = "browser_crashed"
    URL_BLOCKED = "url_blocked"
    EVAL_DISABLED = "eval_disabled"
    EXECUTION_ERROR = "execution_error"

class BrowserResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[BrowserErrorCode] = None

class BrowserStatus(BaseModel):
    url: str
    title: str
    load_state: str
    is_healthy: bool
    console_errors: int

# =============================================================================
# URL VALIDATION
# =============================================================================

def validate_url(url: str, allow_private: bool = False) -> str:
    """Validate URL for SSRF prevention including DNS resolution."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    if scheme in BLOCKED_SCHEMES:
        raise ValueError(f"Forbidden scheme: {scheme}")

    if scheme not in ('http', 'https'):
        raise ValueError(f"Forbidden scheme: {scheme}. Only http/https allowed.")

    # Prevent username:password@host syntax which can bypass some parsers
    if parsed.username or parsed.password:
        raise ValueError("URLs with credentials are not allowed for security reasons.")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("Invalid URL: missing hostname")

    if not allow_private:
        # 1. Static host check
        if hostname.lower() in BLOCKED_HOSTS or hostname.lower().endswith(('.local', '.internal')):
            raise ValueError(f"Access to {hostname} is blocked.")
        
        # 2. DNS resolution check (prevent DNS rebinding & obfuscated IPs)
        try:
            # Resolve all IP addresses for this hostname
            addr_info = socket.getaddrinfo(hostname, None)
            for info in addr_info:
                ip_str = info[4][0]
                ip = ipaddress.ip_address(ip_str)
                
                for network in PRIVATE_IP_RANGES:
                    if ip in network:
                        raise ValueError(f"Access to private IP {ip_str} (via {hostname}) is blocked.")
        except socket.gaierror:
            # If we can't resolve it, it might be a malformed hostname or unreachable
            # In a strict environment, we might block this, but for now we'll allow 
            # Playwright to handle the failure unless it's an IP literal.
            try:
                ip = ipaddress.ip_address(hostname)
                for network in PRIVATE_IP_RANGES:
                    if ip in network:
                        raise ValueError(f"Access to private IP {hostname} is blocked.")
            except ValueError:
                pass # Not an IP literal, and couldn't resolve via DNS
            
    return url

# =============================================================================
# MCP DRIVER
# =============================================================================

class MCPDriver:
    """Async supervisor for Playwright browser context."""
    
    def __init__(self, headless: bool = True, allow_private: bool = False):
        self.headless = headless
        self.allow_private = allow_private
        self.pw = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.temp_dir = None
        self.console_errors = 0
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the browser and context."""
        if self.pw: return
        
        self.pw = await async_playwright().start()
        self.temp_dir = tempfile.mkdtemp(prefix="agent_browser_mcp_")
        
        self.browser = await self.pw.chromium.launch(
            headless=self.headless,
            args=["--disable-dev-shm-usage", "--no-sandbox"]
        )
        
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        self.page = await self.context.new_page()
        self.page.on("console", self._handle_console)
        self.page.on("pageerror", self._handle_pageerror)
        
        # Intercept and validate all requests for SSRF protection
        await self.context.route("**/*", self._route_interceptor)

    async def _route_interceptor(self, route):
        """SSRF protection at the request level."""
        try:
            validate_url(route.request.url, self.allow_private)
            await route.continue_()
        except ValueError as e:
            logging.warning(f"Blocked request to {route.request.url}: {e}")
            await route.abort("blockedbyclient")

    def _handle_console(self, msg):
        if msg.type == "error":
            self.console_errors += 1

    def _handle_pageerror(self, exc):
        self.console_errors += 1
        logging.error(f"Page error: {exc}")

    async def ensure_healthy(self):
        """Check health and respawn if crashed."""
        if not self.browser or not self.browser.is_connected():
            logging.info("Browser disconnected, respawning...")
            await self.cleanup()
            await self.start()
            return True # Signaled restart
        return False

    async def cleanup(self):
        """Graceful shutdown."""
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.pw: await self.pw.stop()
        self.pw = None
        # Note: temp_dir cleanup could be added here

# =============================================================================
# MCP SERVER
# =============================================================================

mcp = FastMCP("agent-browser", dependencies=["playwright", "pydantic"])
driver: Optional[MCPDriver] = None

@mcp.tool()
async def browser_navigate(url: str) -> BrowserResponse:
    """Navigate to a URL with SSRF protection."""
    async with driver._lock:
        try:
            valid_url = validate_url(url, driver.allow_private)
            await driver.ensure_healthy()
            await driver.page.goto(valid_url, wait_until="domcontentloaded", timeout=30000)
            return BrowserResponse(success=True, message=f"Navigated to {driver.page.url}")
        except ValueError as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.URL_BLOCKED)
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_screenshot(name: Optional[str] = None, include_b64: bool = False) -> BrowserResponse:
    """Take a screenshot. Returns path and optionally base64 WebP data."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name or 'screenshot'}_{timestamp}.webp"
            path = Path("screenshots") / filename
            path.parent.mkdir(exist_ok=True)
            
            await driver.page.screenshot(path=str(path), type="webp", quality=80)
            
            data = {"path": str(path.absolute())}
            if include_b64:
                with open(path, "rb") as f:
                    data["base64_data"] = base64.b64encode(f.read()).decode("utf-8")
            
            return BrowserResponse(success=True, message=f"Screenshot saved to {path}", data=data)
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_click(selector: str) -> BrowserResponse:
    """Click an element."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            await driver.page.click(selector, timeout=10000)
            return BrowserResponse(success=True, message=f"Clicked {selector}")
        except PlaywrightError as e:
            if "Timeout" in str(e):
                return BrowserResponse(success=False, message=f"Selector {selector} not found or not clickable", error_code=BrowserErrorCode.SELECTOR_NOT_FOUND)
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_fill(selector: str, value: str) -> BrowserResponse:
    """Fill an input field."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            await driver.page.fill(selector, value, timeout=10000)
            return BrowserResponse(success=True, message=f"Filled {selector} with {value}")
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_type(selector: str, text: str) -> BrowserResponse:
    """Type text into an element (triggers key events)."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            await driver.page.type(selector, text, delay=50, timeout=10000)
            return BrowserResponse(success=True, message=f"Typed into {selector}")
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_press(key: str) -> BrowserResponse:
    """Press a keyboard key (e.g. Enter, Escape, ArrowDown)."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            await driver.page.keyboard.press(key)
            return BrowserResponse(success=True, message=f"Pressed {key}")
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_scroll(direction: Literal["up", "down", "top", "bottom"]) -> BrowserResponse:
    """Scroll the page."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            if direction == "top":
                await driver.page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                await driver.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "up":
                await driver.page.evaluate("window.scrollBy(0, -500)")
            elif direction == "down":
                await driver.page.evaluate("window.scrollBy(0, 500)")
            return BrowserResponse(success=True, message=f"Scrolled {direction}")
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_wait_for(selector: Optional[str] = None, state: Literal["visible", "hidden", "attached", "detached"] = "visible", timeout: int = 10000) -> BrowserResponse:
    """Wait for an element to reach a specific state."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            if selector:
                await driver.page.wait_for_selector(selector, state=state, timeout=timeout)
                return BrowserResponse(success=True, message=f"Selector {selector} is now {state}")
            else:
                # If no selector, wait for load state
                await driver.page.wait_for_load_state("networkidle", timeout=timeout)
                return BrowserResponse(success=True, message="Page reached networkidle state")
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_text(selector: str) -> BrowserResponse:
    """Extract text content from an element."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            text = await driver.page.text_content(selector, timeout=5000)
            return BrowserResponse(success=True, message="Text extracted", data={"text": text.strip() if text else ""})
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_hover(selector: str) -> BrowserResponse:
    """Hover over an element."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            await driver.page.hover(selector, timeout=5000)
            return BrowserResponse(success=True, message=f"Hovering over {selector}")
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_handle_dialog(action: Literal["accept", "dismiss"], prompt_text: Optional[str] = None) -> BrowserResponse:
    """Handle an active dialog (alert, confirm, prompt)."""
    async with driver._lock:
        # Note: In Playwright, dialogs are often handled via event listeners
        # For this tool, we'll implement a simple one-time handler if a dialog is pending
        # This is a simplified version; a full implementation might need more state.
        return BrowserResponse(success=False, message="Dialog handling via tool not fully implemented in this version. Use automated listeners.", error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_query(selector: str) -> BrowserResponse:
    """Query elements and return a simplified representation (accessibility tree fragment)."""
    async with driver._lock:
        try:
            await driver.ensure_healthy()
            # This returns a simplified view of the element and its children
            js_query = """
            (selector) => {
                const el = document.querySelector(selector);
                if (!el) return null;
                const mapEl = (node) => {
                    if (node.nodeType !== 1) return null;
                    return {
                        tag: node.tagName.toLowerCase(),
                        id: node.id,
                        classes: node.className,
                        text: node.innerText?.slice(0, 100),
                        role: node.getAttribute('role'),
                        children: Array.from(node.children).map(mapEl).filter(n => n !== null).slice(0, 10)
                    };
                };
                return mapEl(el);
            }
            """
            result = await driver.page.evaluate(js_query, selector)
            if not result:
                return BrowserResponse(success=False, message=f"Selector {selector} not found", error_code=BrowserErrorCode.SELECTOR_NOT_FOUND)
            return BrowserResponse(success=True, message="Query successful", data=result)
        except Exception as e:
            return BrowserResponse(success=False, message=str(e), error_code=BrowserErrorCode.EXECUTION_ERROR)

@mcp.tool()
async def browser_get_logs() -> BrowserResponse:
    """Retrieve console logs and cumulative error count."""
    async with driver._lock:
        return BrowserResponse(
            success=True, 
            message="Logs retrieved", 
            data={
                "console_errors": driver.console_errors,
                "status": "ready"
            }
        )

@mcp.tool()
async def browser_status() -> BrowserStatus:
    """Get current browser status."""
    return BrowserStatus(
        url=driver.page.url if driver.page else "none",
        title=await driver.page.title() if driver.page else "none",
        load_state="ready", # Simplified for now
        is_healthy=driver.browser.is_connected() if driver.browser else False,
        console_errors=driver.console_errors
    )

def main():
    import argparse
    parser = argparse.ArgumentParser(description="agent-browser MCP server")
    parser.add_argument("--visible", action="store_true", help="Run headed")
    parser.add_argument("--allow-private", action="store_true", help="Allow private IPs")
    args = parser.parse_args()

    global driver
    driver = MCPDriver(headless=not args.visible, allow_private=args.allow_private)
    
    # Use a simple startup to initialize the driver before MCP runs
    loop = asyncio.get_event_loop()
    loop.run_until_complete(driver.start())
    
    mcp.run()

if __name__ == "__main__":
    main()
