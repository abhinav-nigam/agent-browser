"""
Shared utilities for agent-browser.

This module contains utility functions used across the package, including:
- Screenshot resizing
- State file management
- Process management
- Logging utilities
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# =============================================================================
# CONFIGURATION DEFAULTS
# =============================================================================

MAX_SCREENSHOT_HEIGHT = 1500
MAX_SCREENSHOT_WIDTH = 1500
DEFAULT_TIMEOUT = 5000
WAIT_FOR_TIMEOUT = 10000
IPC_TIMEOUT = 10

# =============================================================================
# GENERAL UTILITIES
# =============================================================================


def sanitize_filename(name: str) -> str:
    """Return a safe filename by replacing path separators."""
    return name.replace("/", "_").replace("\\", "_")


# =============================================================================
# FILE PATH HELPERS
# =============================================================================


def get_temp_file_path(session_id: str, suffix: str) -> Path:
    return Path(tempfile.gettempdir()) / f"agent_browser_{session_id}_{suffix}"


def get_state_file(session_id: str) -> Path:
    return get_temp_file_path(session_id, "state.json")


def get_command_file(session_id: str) -> Path:
    return get_temp_file_path(session_id, "cmd.json")


def get_result_file(session_id: str) -> Path:
    return get_temp_file_path(session_id, "result.json")


def get_console_log_file(session_id: str) -> Path:
    return get_temp_file_path(session_id, "console.json")


def get_network_log_file(session_id: str) -> Path:
    return get_temp_file_path(session_id, "network.json")


def get_pid_file(session_id: str) -> Path:
    return get_temp_file_path(session_id, "pid.txt")


# =============================================================================
# SCREENSHOT UTILITIES
# =============================================================================


def resize_screenshot_if_needed(filepath: Path) -> str:
    try:
        from PIL import Image
        img = Image.open(filepath)
        width, height = img.size
        if height <= MAX_SCREENSHOT_HEIGHT and width <= MAX_SCREENSHOT_WIDTH:
            return f"{width}x{height} (ok)"
        ratio = min(MAX_SCREENSHOT_WIDTH / width, MAX_SCREENSHOT_HEIGHT / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        img_resized = img.resize((new_width, new_height), Image.LANCZOS)
        img_resized.save(filepath, optimize=True)
        return f"{width}x{height} -> {new_width}x{new_height} (resized)"
    except ImportError:
        return "not resized (PIL not installed)"
    except Exception as e:
        return f"resize error: {e}"


# =============================================================================
# STATE MANAGEMENT
# =============================================================================


def get_state(session_id: str) -> Dict[str, Any]:
    state_file = get_state_file(session_id)
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(session_id: str, state: Dict[str, Any]) -> None:
    state_file = get_state_file(session_id)
    state_file.write_text(json.dumps(state, indent=2))


def clear_state(session_id: str) -> None:
    files = [
        get_state_file(session_id),
        get_command_file(session_id),
        get_result_file(session_id),
        get_console_log_file(session_id),
        get_network_log_file(session_id),
        get_pid_file(session_id),
    ]
    for f in files:
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass


# =============================================================================
# PROCESS MANAGEMENT
# =============================================================================


def is_process_running(pid: int) -> bool:
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def get_browser_pid(session_id: str) -> Optional[int]:
    pid_file = get_pid_file(session_id)
    if pid_file.exists():
        try:
            return int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return None
    return None


def save_browser_pid(session_id: str) -> None:
    pid_file = get_pid_file(session_id)
    pid_file.write_text(str(os.getpid()))


# =============================================================================
# LOGGING UTILITIES
# =============================================================================


def get_console_logs(session_id: str) -> List[Dict[str, Any]]:
    log_file = get_console_log_file(session_id)
    if log_file.exists():
        try:
            return json.loads(log_file.read_text())
        except json.JSONDecodeError:
            return []
    return []


def save_console_log(session_id: str, entry: Dict[str, Any]) -> None:
    logs = get_console_logs(session_id)
    logs.append(entry)
    if len(logs) > 100:
        logs = logs[-100:]
    log_file = get_console_log_file(session_id)
    log_file.write_text(json.dumps(logs, indent=2))


def get_network_logs(session_id: str) -> Dict[str, Dict[str, Any]]:
    log_file = get_network_log_file(session_id)
    if log_file.exists():
        try:
            return json.loads(log_file.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_network_logs(session_id: str, logs: Dict[str, Dict[str, Any]]) -> None:
    if len(logs) > 100:
        sorted_keys = sorted(logs.keys(), key=lambda k: logs[k].get("start_time", ""))
        for key in sorted_keys[:-100]:
            del logs[key]
    log_file = get_network_log_file(session_id)
    log_file.write_text(json.dumps(logs, indent=2))


def add_network_request(session_id: str, request_id: str, entry: Dict[str, Any]) -> None:
    logs = get_network_logs(session_id)
    if request_id in logs:
        logs[request_id].update(entry)
    else:
        logs[request_id] = entry
    save_network_logs(session_id, logs)


def clear_logs(session_id: str) -> None:
    for f in [get_console_log_file(session_id), get_network_log_file(session_id)]:
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass


# =============================================================================
# FORMATTING UTILITIES
# =============================================================================


def format_assertion_result(passed: bool, message: str) -> str:
    status = "PASS" if passed else "FAIL"
    return f"[{status}] {message}"


def configure_windows_console() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
