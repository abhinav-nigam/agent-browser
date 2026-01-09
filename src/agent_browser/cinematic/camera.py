"""
Camera control tools for the Cinematic Engine.

Provides zoom and pan effects using CSS transforms on the document,
preserving responsive layouts (unlike viewport resizing).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, TYPE_CHECKING

from .scripts import CAMERA_SCRIPT

if TYPE_CHECKING:
    from playwright.async_api import Page


class CameraMixin:
    """
    Mixin class providing camera control tools.

    Expects the host class to have:
    - self._lock: asyncio.Lock - Thread safety lock
    - self._ensure_page() -> Page - Method to get current page
    """

    _lock: asyncio.Lock

    async def _ensure_page(self) -> "Page":
        """Get the current page, starting browser if needed."""
        raise NotImplementedError("Host class must implement _ensure_page")

    async def camera_zoom(
        self,
        selector: str,
        level: float = 1.5,
        duration_ms: int = 800,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Zoom the camera to focus on an element.

        Uses CSS transforms to scale the document and center the target element,
        creating a "Ken Burns" zoom effect without breaking responsive layouts.

        Args:
            selector: CSS selector for the element to zoom into
            level: Zoom level (1.0 = normal, 1.5 = 50% zoom, 2.0 = 100% zoom)
            duration_ms: Animation duration in milliseconds

        Returns:
            {"success": True, "data": {"level": 1.5, "target": "selector"}}

        Note: Call camera_reset() to return to normal view.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()

                # Inject camera script
                await page.evaluate(CAMERA_SCRIPT)

                # Escape selector for JavaScript
                escaped_selector = selector.replace("\\", "\\\\").replace("'", "\\'")

                # Execute zoom
                success = await page.evaluate(
                    f"window.__agentCamera.zoom('{escaped_selector}', {level}, {duration_ms})"
                )

                if success:
                    # Wait for animation to complete
                    await asyncio.sleep(duration_ms / 1000 + 0.05)
                    return {
                        "success": True,
                        "message": f"Zoomed to {selector} at {level}x",
                        "data": {
                            "level": level,
                            "target": selector,
                            "duration_ms": duration_ms,
                        },
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Element not found: {selector}",
                    }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Camera zoom failed: {exc}"}

    async def camera_pan(
        self,
        selector: str,
        duration_ms: int = 800,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Pan the camera to center on an element.

        Translates the document to center the target element without zooming,
        useful for following action across the page.

        Args:
            selector: CSS selector for the element to center on
            duration_ms: Animation duration in milliseconds

        Returns:
            {"success": True, "data": {"target": "selector"}}

        Note: Call camera_reset() to return to normal view.
        """

        try:
            async with self._lock:
                page = await self._ensure_page()

                # Inject camera script
                await page.evaluate(CAMERA_SCRIPT)

                # Escape selector for JavaScript
                escaped_selector = selector.replace("\\", "\\\\").replace("'", "\\'")

                # Execute pan
                success = await page.evaluate(
                    f"window.__agentCamera.pan('{escaped_selector}', {duration_ms})"
                )

                if success:
                    # Wait for animation to complete
                    await asyncio.sleep(duration_ms / 1000 + 0.05)
                    return {
                        "success": True,
                        "message": f"Panned to {selector}",
                        "data": {
                            "target": selector,
                            "duration_ms": duration_ms,
                        },
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Element not found: {selector}",
                    }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Camera pan failed: {exc}"}

    async def camera_reset(
        self,
        duration_ms: int = 600,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Reset the camera to normal view.

        Smoothly animates back to 1.0 scale with no translation,
        undoing any previous zoom or pan effects.

        Args:
            duration_ms: Animation duration in milliseconds

        Returns:
            {"success": True, "message": "Camera reset to normal view"}
        """

        try:
            async with self._lock:
                page = await self._ensure_page()

                # Inject camera script
                await page.evaluate(CAMERA_SCRIPT)

                # Execute reset
                await page.evaluate(f"window.__agentCamera.reset({duration_ms})")

                # Wait for animation to complete
                await asyncio.sleep(duration_ms / 1000 + 0.05)

                return {
                    "success": True,
                    "message": "Camera reset to normal view",
                    "data": {"duration_ms": duration_ms},
                }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Camera reset failed: {exc}"}
