"""
Annotation tools for the Cinematic Engine.

Provides floating text annotations that appear on screen during recording
to highlight features or explain what's happening.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from .scripts import ANNOTATION_SCRIPT

if TYPE_CHECKING:
    from playwright.async_api import Page


class AnnotationMixin:
    """
    Mixin class providing annotation tools.

    Expects the host class to have:
    - self._lock: asyncio.Lock - Thread safety lock
    - self._ensure_page() -> Page - Method to get current page
    """

    _lock: asyncio.Lock

    async def _ensure_page(self) -> "Page":
        """Get the current page, starting browser if needed."""
        raise NotImplementedError("Host class must implement _ensure_page")

    async def annotate(
        self,
        text: str,
        target: Optional[str] = None,
        position: str = "above",
        style: str = "light",
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Add a floating text annotation to the video.

        Annotations are visual labels that appear on screen during recording
        to highlight features or explain what's happening.

        Args:
            text: The annotation text to display
            target: Optional CSS selector to position near (if omitted, uses center)
            position: Where to place relative to target: "above", "below", "left", "right"
            style: Visual style: "light" (white bg) or "dark" (dark bg)
            duration_ms: Auto-remove after ms (0 = permanent until clear_annotations)

        Returns:
            {"success": True, "data": {"id": "...", "position": {...}}}
        """

        try:
            async with self._lock:
                page = await self._ensure_page()

                # Inject annotation script
                await page.evaluate(ANNOTATION_SCRIPT)

                # Calculate position
                x, y = 100, 100  # Default position

                if target:
                    try:
                        box = await page.locator(target).first.bounding_box()
                        if box:
                            if position == "above":
                                x = box["x"] + box["width"] / 2 - 75
                                y = box["y"] - 50
                            elif position == "below":
                                x = box["x"] + box["width"] / 2 - 75
                                y = box["y"] + box["height"] + 10
                            elif position == "left":
                                x = box["x"] - 170
                                y = box["y"] + box["height"] / 2 - 20
                            elif position == "right":
                                x = box["x"] + box["width"] + 10
                                y = box["y"] + box["height"] / 2 - 20
                    except Exception:  # pylint: disable=broad-except
                        pass
                else:
                    # Center of viewport
                    viewport = page.viewport_size
                    if viewport:
                        x = viewport["width"] / 2 - 75
                        y = viewport["height"] / 2 - 20

                # Generate unique ID
                annotation_id = f"__annotation_{int(time.time() * 1000)}__"

                # Escape text for JavaScript
                escaped_text = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")

                # Add annotation
                await page.evaluate(
                    f"window.__agentAnnotations.add('{annotation_id}', '{escaped_text}', {x}, {y}, '{style}', {duration_ms})"
                )

                return {
                    "success": True,
                    "message": f"Added annotation: {text[:30]}...",
                    "data": {
                        "id": annotation_id,
                        "position": {"x": x, "y": y},
                        "style": style,
                        "duration_ms": duration_ms,
                    },
                }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Failed to add annotation: {exc}"}

    async def clear_annotations(self) -> Dict[str, Any]:
        """
        [Cinematic Engine] Remove all annotations from the page.

        Returns:
            {"success": True, "message": "Cleared all annotations"}
        """

        try:
            async with self._lock:
                page = await self._ensure_page()
                await page.evaluate(ANNOTATION_SCRIPT)
                await page.evaluate("window.__agentAnnotations.clear()")

                return {
                    "success": True,
                    "message": "Cleared all annotations",
                }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Failed to clear annotations: {exc}"}
