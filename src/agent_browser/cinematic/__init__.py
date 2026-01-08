"""
Cinematic Engine - Video production tools for AI agents.

This package provides tools for creating marketing-grade video content:
- Phase 1: Voice & Timing (TTS, audio duration)
- Phase 2: Recording & Virtual Actor (video capture, cursor, annotations)
- Phase 3: Camera Control (zoom, pan)
- Phase 4: Post-Production (audio/video merging, background music)
- Phase 5: Polish (smooth scrolling, human-like typing, presentation mode)

Usage:
    class BrowserServer(CinematicMixin):
        def __init__(self):
            # Initialize cinematic state
            self._init_cinematic_state()
            ...

    # Then register tools:
    server.tool()(self.generate_voiceover)
    server.tool()(self.start_recording)
    ...
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from .tts import TTSMixin
from .recording import RecordingMixin
from .annotations import AnnotationMixin
from .camera import CameraMixin
from .postproduction import PostProductionMixin
from .polish import PolishMixin

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

__all__ = [
    "CinematicMixin",
    "TTSMixin",
    "RecordingMixin",
    "AnnotationMixin",
    "CameraMixin",
    "PostProductionMixin",
    "PolishMixin",
]


class CinematicMixin(TTSMixin, RecordingMixin, AnnotationMixin, CameraMixin, PostProductionMixin, PolishMixin):
    """
    Combined mixin providing all Cinematic Engine tools.

    Inherit from this class to add video production capabilities to your
    browser automation server.

    Required state variables (call _init_cinematic_state() in __init__):
    - _tts_client: Optional[Any] - Lazy-loaded TTS client
    - _audio_cache_dir: Path - Directory for cached audio files
    - _recording: bool - Recording state flag
    - _video_dir: Path - Directory for video files
    - _video_path: Optional[Path] - Current video file path
    - _recording_start_time: Optional[float] - Recording start timestamp
    - _cursor_injected: bool - Whether cursor is injected
    - _saved_url: Optional[str] - URL saved before context recreation
    - _lock: asyncio.Lock - Thread safety lock

    Required from host class:
    - browser: Optional[Browser] - Playwright browser
    - context: Optional[BrowserContext] - Browser context
    - page: Optional[Page] - Current page
    - headless: bool - Headless mode flag
    - start(headless: bool) - Method to start browser
    - _ensure_page() -> Page - Method to get current page
    - _handle_console - Console event handler
    - _handle_request_finished - Network event handler
    """

    # Type hints for state variables
    _tts_client: Optional[Any]
    _audio_cache_dir: Path
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

    def _init_cinematic_state(self) -> None:
        """
        Initialize all Cinematic Engine state variables.

        Call this in your __init__ method before _register_tools().
        """
        # Phase 1: Voice & Timing
        self._tts_client: Optional[Any] = None
        self._audio_cache_dir = Path("audio_cache")

        # Phase 2: Recording & Virtual Actor
        self._recording = False
        self._video_dir = Path("videos")
        self._video_path: Optional[Path] = None
        self._recording_start_time: Optional[float] = None
        self._cursor_injected = False
        self._saved_url: Optional[str] = None

    def _register_cinematic_tools(self, server: Any) -> None:
        """
        Register all Cinematic Engine tools with the MCP server.

        Call this in your _register_tools() method.

        Args:
            server: FastMCP server instance
        """
        # Phase 1: Voice & Timing
        server.tool()(self.generate_voiceover)
        server.tool()(self.get_audio_duration)

        # Phase 2: Recording & Virtual Actor
        server.tool()(self.start_recording)
        server.tool()(self.stop_recording)
        server.tool()(self.recording_status)
        server.tool()(self.annotate)
        server.tool()(self.clear_annotations)

        # Phase 3: Camera Control
        server.tool()(self.camera_zoom)
        server.tool()(self.camera_pan)
        server.tool()(self.camera_reset)

        # Phase 4: Post-Production
        server.tool()(self.check_environment)
        server.tool()(self.merge_audio_video)
        server.tool()(self.add_background_music)
        server.tool()(self.get_video_duration)

        # Phase 5: Polish
        server.tool()(self.smooth_scroll)
        server.tool()(self.type_human)
        server.tool()(self.set_presentation_mode)
        server.tool()(self.freeze_time)
