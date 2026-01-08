"""
Video recording tools for the Cinematic Engine.

Provides browser video recording with virtual cursor injection
and automatic URL restoration after context recreation.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from .scripts import CURSOR_SCRIPT

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page


class RecordingMixin:
    """
    Mixin class providing video recording tools.

    Expects the host class to have:
    - self._recording: bool - Recording state flag
    - self._video_dir: Path - Directory for video files
    - self._video_path: Optional[Path] - Current video file path
    - self._recording_start_time: Optional[float] - Recording start timestamp
    - self._cursor_injected: bool - Whether cursor is injected
    - self._saved_url: Optional[str] - URL saved before context recreation
    - self._lock: asyncio.Lock - Thread safety lock
    - self.browser: Optional[Browser] - Playwright browser
    - self.context: Optional[BrowserContext] - Browser context
    - self.page: Optional[Page] - Current page
    - self.headless: bool - Headless mode flag
    - self.start(headless: bool) - Method to start browser
    - self._handle_console - Console event handler
    - self._handle_request_finished - Network event handler
    """

    # State variables (initialized by host class)
    _recording: bool
    _video_dir: Path
    _video_path: Optional[Path]
    _recording_start_time: Optional[float]
    _cursor_injected: bool
    _saved_url: Optional[str]
    _lock: asyncio.Lock
    browser: Optional["Browser"]
    context: Optional["BrowserContext"]
    page: Optional["Page"]
    headless: bool

    async def _inject_cursor(self) -> None:
        """Inject the virtual cursor overlay into the page."""
        if not self.page:
            return
        await self.page.evaluate(CURSOR_SCRIPT)
        self._cursor_injected = True

    async def _move_cursor_to_element(self, selector: str, duration_ms: int = 200) -> bool:
        """Move the virtual cursor to the center of an element."""
        if not self._recording or not self.page:
            return False

        try:
            # Get element bounding box
            box = await self.page.locator(selector).first.bounding_box()
            if not box:
                return False

            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2

            # Move cursor
            await self.page.evaluate(
                f"window.__agentCursor?.moveTo({x}, {y}, {duration_ms})"
            )
            # Wait for animation
            await asyncio.sleep(duration_ms / 1000 + 0.05)
            return True
        except Exception:  # pylint: disable=broad-except
            return False

    async def _click_effect(self, x: float, y: float) -> None:
        """Show click ripple effect at coordinates."""
        if not self._recording or not self.page:
            return
        try:
            await self.page.evaluate(f"window.__agentCursor?.click({x}, {y})")
        except Exception:  # pylint: disable=broad-except
            pass

    async def start_recording(
        self,
        filename: str = "recording",
        width: int = 1920,
        height: int = 1080,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Start video recording of the browser.

        Creates a new browser context with video recording enabled. The current
        page URL is preserved and restored after context recreation.

        Args:
            filename: Output filename (without extension)
            width: Video width in pixels (default 1920 for 1080p)
            height: Video height in pixels (default 1080 for 1080p)

        Returns:
            {"success": True, "data": {"video_dir": "...", "viewport": {...}}}

        Note: Recording uses Playwright's built-in video capture. The virtual
        cursor is automatically injected and will animate during interactions.
        """

        try:
            async with self._lock:
                if self._recording:
                    return {
                        "success": False,
                        "message": "Already recording. Call stop_recording() first.",
                    }

                # Ensure video directory exists
                self._video_dir.mkdir(parents=True, exist_ok=True)

                # Save current URL to restore after context recreation
                self._saved_url = None
                if self.page:
                    try:
                        self._saved_url = self.page.url
                        if self._saved_url == "about:blank":
                            self._saved_url = None
                    except Exception:  # pylint: disable=broad-except
                        pass

                # Close existing context (required for video recording)
                if self.context:
                    await self.context.close()
                    self.context = None
                    self.page = None

                # Ensure browser is started
                if not self.browser:
                    await self.start(headless=self.headless)

                # Create new context with video recording
                self.context = await self.browser.new_context(
                    viewport={"width": width, "height": height},
                    record_video_dir=str(self._video_dir),
                    record_video_size={"width": width, "height": height},
                )

                # Create new page
                self.page = await self.context.new_page()

                # Re-attach event handlers
                self.context.on("console", self._handle_console)
                self.context.on(
                    "requestfinished",
                    lambda req: asyncio.create_task(self._handle_request_finished(req)),
                )

                # Inject cursor overlay
                await self._inject_cursor()

                # Restore URL if we had one
                if self._saved_url:
                    await self.page.goto(self._saved_url)
                    # Re-inject cursor after navigation
                    await self._inject_cursor()

                self._recording = True
                self._recording_start_time = time.time()
                self._video_path = None  # Will be set when recording stops

                return {
                    "success": True,
                    "message": f"Recording started at {width}x{height}",
                    "data": {
                        "video_dir": str(self._video_dir.resolve()),
                        "viewport": {"width": width, "height": height},
                        "restored_url": self._saved_url,
                    },
                }

        except Exception as exc:  # pylint: disable=broad-except
            self._recording = False
            return {"success": False, "message": f"Failed to start recording: {exc}"}

    async def stop_recording(self) -> Dict[str, Any]:
        """
        [Cinematic Engine] Stop video recording and return the video file path.

        Closes the recording context and retrieves the generated video file.
        The video is saved as WebM format by Playwright.

        Returns:
            {"success": True, "data": {"path": "...", "duration_sec": ...}}
        """

        try:
            async with self._lock:
                if not self._recording:
                    return {
                        "success": False,
                        "message": "Not currently recording. Call start_recording() first.",
                    }

                if not self.page:
                    return {"success": False, "message": "No page available"}

                # Get the video path before closing
                video = self.page.video
                if not video:
                    return {"success": False, "message": "No video object available"}

                # Calculate duration
                duration_sec = 0.0
                if self._recording_start_time:
                    duration_sec = round(time.time() - self._recording_start_time, 2)

                # Save the video path
                video_path = await video.path()

                # Close the context to finalize the video
                await self.context.close()
                self.context = None
                self.page = None

                self._recording = False
                self._recording_start_time = None
                self._cursor_injected = False
                self._video_path = Path(video_path) if video_path else None

                if self._video_path and self._video_path.exists():
                    file_size = self._video_path.stat().st_size
                    return {
                        "success": True,
                        "message": f"Recording saved: {self._video_path.name}",
                        "data": {
                            "path": str(self._video_path.resolve()),
                            "duration_sec": duration_sec,
                            "size_bytes": file_size,
                        },
                    }
                else:
                    return {
                        "success": False,
                        "message": "Video file not found after recording",
                    }

        except Exception as exc:  # pylint: disable=broad-except
            self._recording = False
            return {"success": False, "message": f"Failed to stop recording: {exc}"}

    async def recording_status(self) -> Dict[str, Any]:
        """
        [Cinematic Engine] Get current recording status.

        Returns:
            {"success": True, "data": {"recording": bool, "duration_sec": ..., "video_dir": ...}}
        """

        duration_sec = 0.0
        if self._recording and self._recording_start_time:
            duration_sec = round(time.time() - self._recording_start_time, 2)

        return {
            "success": True,
            "message": "Recording" if self._recording else "Not recording",
            "data": {
                "recording": self._recording,
                "duration_sec": duration_sec,
                "video_dir": str(self._video_dir.resolve()),
                "cursor_injected": self._cursor_injected,
            },
        }
