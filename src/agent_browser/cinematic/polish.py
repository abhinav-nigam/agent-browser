"""
Polish tools for the Cinematic Engine.

Provides human-like interactions and presentation enhancements
for professional-quality video production.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, Optional, TYPE_CHECKING

from .scripts import PRESENTATION_MODE_SCRIPT

if TYPE_CHECKING:
    from playwright.async_api import Page


# JavaScript for smooth scrolling with easing
SMOOTH_SCROLL_SCRIPT = """
window.__agentScroll = {
    smoothTo: (targetY, duration) => {
        return new Promise(resolve => {
            const startY = window.scrollY;
            const distance = targetY - startY;
            const startTime = performance.now();

            function step(currentTime) {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);

                // Ease-out-cubic for natural deceleration
                const easeProgress = 1 - Math.pow(1 - progress, 3);
                window.scrollTo(0, startY + distance * easeProgress);

                if (progress < 1) {
                    requestAnimationFrame(step);
                } else {
                    resolve();
                }
            }

            requestAnimationFrame(step);
        });
    },
    smoothBy: (deltaY, duration) => {
        const targetY = window.scrollY + deltaY;
        return window.__agentScroll.smoothTo(targetY, duration);
    }
};
"""

# JavaScript for human-like typing simulation
HUMAN_TYPE_SCRIPT = """
window.__agentType = {
    human: async (selector, text, wpm, variance) => {
        const el = document.querySelector(selector);
        if (!el) return false;

        el.focus();

        // Calculate base delay from WPM (average 5 chars per word)
        const baseDelay = (60 * 1000) / (wpm * 5);

        for (let i = 0; i < text.length; i++) {
            const char = text[i];

            // Add variance to timing
            const varianceFactor = 1 + (Math.random() - 0.5) * variance;
            let delay = baseDelay * varianceFactor;

            // Longer pauses after punctuation
            if (['.', '!', '?'].includes(char)) {
                delay *= 3;
            } else if ([',', ';', ':'].includes(char)) {
                delay *= 1.5;
            }

            // Type the character
            el.value += char;
            el.dispatchEvent(new Event('input', { bubbles: true }));

            await new Promise(r => setTimeout(r, delay));
        }

        return true;
    }
};
"""


class PolishMixin:
    """
    Mixin class providing polish and human-like interaction tools.

    Expects the host class to have:
    - self._lock: asyncio.Lock - Thread safety lock
    - self._ensure_page() -> Page - Method to get current page
    """

    _lock: asyncio.Lock
    _presentation_mode: bool = False

    async def _ensure_page(self) -> "Page":
        """Get the current page, starting browser if needed."""
        raise NotImplementedError("Host class must implement _ensure_page")

    async def smooth_scroll(
        self,
        direction: str = "down",
        amount: int = 500,
        duration_ms: int = 800,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Smoothly scroll the page with eased animation.

        Unlike the standard scroll tool which jumps instantly, this provides
        smooth, cinematic scrolling perfect for video recording.

        Args:
            direction: "up", "down", "top", or "bottom"
            amount: Pixels to scroll (for "up"/"down" only)
            duration_ms: Animation duration in milliseconds

        Returns:
            {"success": True, "data": {"direction": "down", "scrolled_to": 500}}
        """
        try:
            async with self._lock:
                page = await self._ensure_page()

                # Inject smooth scroll script
                await page.evaluate(SMOOTH_SCROLL_SCRIPT)

                if direction == "top":
                    await page.evaluate(
                        f"window.__agentScroll.smoothTo(0, {duration_ms})"
                    )
                    target = 0
                elif direction == "bottom":
                    await page.evaluate(
                        f"window.__agentScroll.smoothTo(document.body.scrollHeight, {duration_ms})"
                    )
                    target = "bottom"
                elif direction == "down":
                    await page.evaluate(
                        f"window.__agentScroll.smoothBy({amount}, {duration_ms})"
                    )
                    target = f"+{amount}px"
                elif direction == "up":
                    await page.evaluate(
                        f"window.__agentScroll.smoothBy({-amount}, {duration_ms})"
                    )
                    target = f"-{amount}px"
                else:
                    return {
                        "success": False,
                        "message": f"Invalid direction: {direction}. Use 'up', 'down', 'top', or 'bottom'",
                    }

                # Wait for animation to complete
                await asyncio.sleep(duration_ms / 1000 + 0.05)

                return {
                    "success": True,
                    "message": f"Smoothly scrolled {direction}",
                    "data": {
                        "direction": direction,
                        "scrolled_to": target,
                        "duration_ms": duration_ms,
                    },
                }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Smooth scroll failed: {exc}"}

    async def type_human(
        self,
        selector: str,
        text: str,
        wpm: int = 60,
        variance: float = 0.3,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Type text with human-like timing and rhythm.

        Simulates realistic typing with variable speed, pauses after
        punctuation, and natural rhythm variance.

        Args:
            selector: CSS selector for the input element
            text: Text to type
            wpm: Words per minute (default 60, average typing speed)
            variance: Timing variance factor (0.0-1.0, default 0.3 = 30% variation)

        Returns:
            {"success": True, "data": {"typed": "...", "wpm": 60}}

        Note: For video recording, this creates a realistic typing effect
        that looks natural rather than instant text insertion.
        """
        try:
            async with self._lock:
                page = await self._ensure_page()

                # Check element exists
                element = page.locator(selector).first
                if not await element.count():
                    return {
                        "success": False,
                        "message": f"Element not found: {selector}",
                    }

                # Clear existing content
                await element.fill("")

                # Focus the element
                await element.focus()

                # Calculate timing
                # Average word is 5 characters
                chars_per_minute = wpm * 5
                base_delay_ms = (60 * 1000) / chars_per_minute

                # Type each character with human-like timing
                for char in text:
                    # Add variance to timing
                    variance_factor = 1 + (random.random() - 0.5) * variance
                    delay = base_delay_ms * variance_factor

                    # Longer pauses after punctuation
                    if char in ".!?":
                        delay *= 3
                    elif char in ",;:":
                        delay *= 1.5
                    elif char == " ":
                        delay *= 1.2

                    # Type the character
                    await page.keyboard.type(char)
                    await asyncio.sleep(delay / 1000)

                return {
                    "success": True,
                    "message": f"Typed {len(text)} characters at ~{wpm} WPM",
                    "data": {
                        "typed": text[:50] + "..." if len(text) > 50 else text,
                        "length": len(text),
                        "wpm": wpm,
                        "variance": variance,
                    },
                }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Human typing failed: {exc}"}

    async def set_presentation_mode(
        self,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Enable or disable presentation mode.

        Presentation mode optimizes the page for video recording:
        - Hides scrollbars for cleaner visuals
        - Enables smooth scrolling CSS
        - Creates a polished, demo-ready appearance

        Args:
            enabled: True to enable, False to disable

        Returns:
            {"success": True, "data": {"presentation_mode": True}}
        """
        try:
            async with self._lock:
                page = await self._ensure_page()

                if enabled:
                    await page.evaluate(PRESENTATION_MODE_SCRIPT)
                    self._presentation_mode = True
                else:
                    # Remove presentation mode styles
                    await page.evaluate("""
                        const style = document.getElementById('__agent_presentation__');
                        if (style) style.remove();
                    """)
                    self._presentation_mode = False

                return {
                    "success": True,
                    "message": f"Presentation mode {'enabled' if enabled else 'disabled'}",
                    "data": {"presentation_mode": enabled},
                }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Presentation mode failed: {exc}"}

    async def freeze_time(
        self,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Freeze or restore the page's time.

        Useful for demos where you want consistent timestamps,
        or to hide the fact that a recording took multiple takes.

        Args:
            timestamp: ISO timestamp to freeze at (e.g., "2024-01-15T10:30:00")
                      If None, restores normal time behavior

        Returns:
            {"success": True, "data": {"frozen_at": "2024-01-15T10:30:00"}}
        """
        try:
            async with self._lock:
                page = await self._ensure_page()

                if timestamp:
                    # Parse and validate timestamp
                    try:
                        # Inject time freeze
                        await page.evaluate(f"""
                            (() => {{
                                const frozenTime = new Date('{timestamp}').getTime();
                                if (isNaN(frozenTime)) throw new Error('Invalid timestamp');

                                // Store original
                                if (!window.__originalDate) {{
                                    window.__originalDate = Date;
                                }}

                                // Override Date
                                const FrozenDate = function(...args) {{
                                    if (args.length === 0) {{
                                        return new window.__originalDate(frozenTime);
                                    }}
                                    return new window.__originalDate(...args);
                                }};
                                FrozenDate.now = () => frozenTime;
                                FrozenDate.parse = window.__originalDate.parse;
                                FrozenDate.UTC = window.__originalDate.UTC;
                                FrozenDate.prototype = window.__originalDate.prototype;

                                window.Date = FrozenDate;
                            }})();
                        """)

                    except Exception:
                        return {
                            "success": False,
                            "message": f"Invalid timestamp format: {timestamp}",
                        }

                    return {
                        "success": True,
                        "message": f"Time frozen at {timestamp}",
                        "data": {"frozen_at": timestamp},
                    }
                else:
                    # Restore normal time
                    await page.evaluate("""
                        if (window.__originalDate) {
                            window.Date = window.__originalDate;
                            delete window.__originalDate;
                        }
                    """)

                    return {
                        "success": True,
                        "message": "Time restored to normal",
                        "data": {"frozen_at": None},
                    }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Freeze time failed: {exc}"}
