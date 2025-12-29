"""
agent-browser: A robust browser automation tool for AI agents.

Control browsers via CLI or IPC with support for screenshots, interactions,
assertions, and data extraction. Also provides an MCP (Model Context Protocol)
server for integration with AI assistants like Claude.
"""

from .driver import BrowserDriver
from .interactive import InteractiveRunner
from .mcp import BrowserServer, URLValidator
from .utils import (
    PathTraversalError,
    resize_screenshot_if_needed,
    sanitize_filename,
    validate_path,
    validate_path_in_sandbox,
    validate_output_dir,
)

__version__ = "0.1.6"
__all__ = [
    "BrowserDriver",
    "BrowserServer",
    "InteractiveRunner",
    "PathTraversalError",
    "URLValidator",
    "resize_screenshot_if_needed",
    "sanitize_filename",
    "validate_path",
    "validate_path_in_sandbox",
    "validate_output_dir",
]
