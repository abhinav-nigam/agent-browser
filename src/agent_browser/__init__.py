"""
agent-browser: A robust browser automation tool for AI agents.

Control browsers via CLI or IPC with support for screenshots, interactions,
assertions, and data extraction.
"""

from .driver import BrowserDriver
from .interactive import InteractiveRunner
from .utils import resize_screenshot_if_needed

__version__ = "0.1.0"
__all__ = ["BrowserDriver", "InteractiveRunner", "resize_screenshot_if_needed"]
