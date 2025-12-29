"""
Shared utilities for the agent-browser package.

Helpers cover path sanitization, simple IPC file handling for the driver,
and lightweight logging helpers for screenshots and console/network events.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, MutableMapping, Union

LOGGER = logging.getLogger(__name__)

IPC_TIMEOUT = 10
DEFAULT_TIMEOUT = 5000
WAIT_FOR_TIMEOUT = 10_000
CONSOLE_LOG_LIMIT = 100

BASE_DIR = Path(".agent_browser")
BASE_DIR.mkdir(parents=True, exist_ok=True)


class PathTraversalError(ValueError):
    """
    Raised when a path escapes the current working directory sandbox.
    """


def configure_windows_console() -> None:
    """
    Enable ANSI colors on Windows terminals where possible.
    """

    if os.name == "nt":
        os.system("")  # type: ignore[arg-type]


def sanitize_filename(name: str) -> str:
    """
    Return a filesystem-safe filename fragment.
    """

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return cleaned or "file"


def _session_dir(session_id: str) -> Path:
    """
    Return the session-specific directory, creating it if missing.
    """

    session_path = BASE_DIR / sanitize_filename(session_id or "default")
    session_path.mkdir(parents=True, exist_ok=True)
    return session_path


def get_command_file(session_id: str) -> Path:
    """
    Path to the IPC command file for the given session.
    """

    return _session_dir(session_id) / "command.json"


def get_result_file(session_id: str) -> Path:
    """
    Path to the IPC result file for the given session.
    """

    return _session_dir(session_id) / "result.json"


def get_state_file(session_id: str) -> Path:
    """
    Path to the persisted state file for the given session.
    """

    return _session_dir(session_id) / "state.json"


def get_console_log_file(session_id: str) -> Path:
    """
    Path to the console log file for the given session.
    """

    return _session_dir(session_id) / "console.json"


def get_network_log_file(session_id: str) -> Path:
    """
    Path to the network log file for the given session.
    """

    return _session_dir(session_id) / "network.json"


def get_pid_file(session_id: str) -> Path:
    """
    Path to the PID file for the given session.
    """

    return _session_dir(session_id) / "pid"


def _read_json(path: Path, default: Union[Dict[str, Any], Iterable[Any]]) -> Any:
    """
    Read JSON from a file, returning a default value if missing or invalid.
    """

    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def save_state(session_id: str, state: MutableMapping[str, Any]) -> None:
    """
    Persist driver state to disk.
    """

    state_file = get_state_file(session_id)
    state_file.write_text(json.dumps(dict(state)))


def get_state(session_id: str) -> Dict[str, Any]:
    """
    Load persisted driver state.
    """

    result = _read_json(get_state_file(session_id), default={})
    return dict(result) if isinstance(result, dict) else {}


def clear_state(session_id: str) -> None:
    """
    Remove persisted state and PID information.
    """

    for path in (get_state_file(session_id), get_pid_file(session_id)):
        try:
            path.unlink()
        except FileNotFoundError:
            continue


def save_console_log(session_id: str, entry: Dict[str, Any]) -> None:
    """
    Append a console log entry to disk.
    """

    log_file = get_console_log_file(session_id)
    logs = get_console_logs(session_id)
    logs.append(entry)
    # Cap at limit
    if len(logs) > CONSOLE_LOG_LIMIT:
        logs = logs[-CONSOLE_LOG_LIMIT:]
    log_file.write_text(json.dumps(logs))


def get_console_logs(session_id: str) -> list:
    """
    Return console log entries for the session.
    """

    data = _read_json(get_console_log_file(session_id), default=[])
    return list(data) if isinstance(data, list) else []


def save_network_logs(session_id: str, logs: Dict[str, Any]) -> None:
    """
    Write network logs to disk.
    """

    get_network_log_file(session_id).write_text(json.dumps(logs))


def get_network_logs(session_id: str) -> Dict[str, Any]:
    """
    Return network logs for the session.
    """

    data = _read_json(get_network_log_file(session_id), default={})
    return dict(data) if isinstance(data, dict) else {}


def add_network_request(session_id: str, request_id: str, payload: Dict[str, Any]) -> None:
    """
    Upsert a network request log entry.
    """

    logs = get_network_logs(session_id)
    logs[request_id] = payload
    save_network_logs(session_id, logs)


def clear_logs(session_id: str) -> None:
    """
    Delete console and network logs.
    """

    for path in (get_console_log_file(session_id), get_network_log_file(session_id)):
        try:
            path.unlink()
        except FileNotFoundError:
            continue


def save_browser_pid(session_id: str) -> None:
    """
    Persist the current process ID for the browser session.
    """

    get_pid_file(session_id).write_text(str(os.getpid()))


def get_browser_pid(session_id: str) -> int:
    """
    Retrieve the saved browser PID or 0 if missing.
    """

    try:
        return int(get_pid_file(session_id).read_text())
    except (FileNotFoundError, ValueError):
        return 0


def is_process_running(pid: int) -> bool:
    """
    Return True if a process with the given PID appears to be running.
    """

    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import psutil  # type: ignore

            return bool(psutil.pid_exists(pid))
        except ImportError:
            # psutil not installed, use Windows API via ctypes
            pass
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:  # pylint: disable=broad-except
            return False
    # Unix: use os.kill with signal 0
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def resize_screenshot_if_needed(path: Union[str, Path], max_dim: int = 2000) -> str:
    """
    Resize a screenshot if Pillow is available and dimensions exceed max_dim.
    """

    try:
        from PIL import Image  # type: ignore
    except Exception:  # pylint: disable=broad-except
        return "skipped"

    filepath = Path(path)
    try:
        with Image.open(filepath) as img:
            width, height = img.size
            if max(width, height) <= max_dim:
                return "unchanged"
            ratio = max_dim / max(width, height)
            new_size = (int(width * ratio), int(height * ratio))
            resized = img.resize(new_size)
            resized.save(filepath)
            return "resized"
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.warning("Failed to resize screenshot %s: %s", filepath, exc)
        return "error"


def format_assertion_result(success: bool, message: str) -> str:
    """
    Format assertion output with a PASS/FAIL prefix.
    """

    prefix = "[PASS]" if success else "[FAIL]"
    return f"{prefix} {message}"


def validate_path(path: Union[str, Path]) -> Path:
    """
    Ensure the path resolves within the current working directory.
    """

    resolved = Path(path).expanduser().resolve()
    cwd = Path.cwd().resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError as exc:
        raise PathTraversalError(f"Path escapes working directory: {resolved}") from exc
    return resolved

def validate_path_in_sandbox(path: Union[str, Path], sandbox: Union[str, Path]) -> Path:
    resolved = Path(path).expanduser().resolve()
    sandbox_resolved = Path(sandbox).expanduser().resolve()
    try:
        resolved.relative_to(sandbox_resolved)
    except ValueError as exc:
        raise PathTraversalError(
            f"Path escapes sandbox: {resolved} is not within {sandbox_resolved}"
        ) from exc
    return resolved


def validate_output_dir(path: Union[str, Path], root: Union[str, Path]) -> Path:
    return validate_path_in_sandbox(path, root)
