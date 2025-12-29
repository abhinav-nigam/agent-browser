"""Tests for utility functions."""

from pathlib import Path

import pytest

from agent_browser.utils import (
    clear_logs,
    clear_state,
    format_assertion_result,
    get_console_logs,
    get_network_logs,
    get_state,
    is_process_running,
    save_console_log,
    save_network_logs,
    save_state,
    sanitize_filename,
    validate_path,
    validate_path_in_sandbox,
    validate_output_dir,
)


class TestSanitizeFilename:
    def test_basic_string(self):
        assert sanitize_filename("test") == "test"

    def test_removes_slashes(self):
        assert sanitize_filename("path/to/file") == "path_to_file"
        assert sanitize_filename("path\\to\\file") == "path_to_file"

    def test_empty_string(self):
        # Empty string should return "file" as a safe default
        assert sanitize_filename("") == "file"


class TestFormatAssertionResult:
    def test_pass(self):
        result = format_assertion_result(True, "Element visible")
        assert result == "[PASS] Element visible"

    def test_fail(self):
        result = format_assertion_result(False, "Element not found")
        assert result == "[FAIL] Element not found"


class TestStateManagement:
    def test_save_and_get_state(self):
        session_id = "test_session_state"
        state = {"running": True, "url": "http://example.com"}

        try:
            save_state(session_id, state)
            retrieved = get_state(session_id)
            assert retrieved == state
        finally:
            clear_state(session_id)

    def test_get_state_nonexistent(self):
        result = get_state("nonexistent_session_12345")
        assert result == {}

    def test_clear_state(self):
        session_id = "test_session_clear"
        save_state(session_id, {"test": True})
        clear_state(session_id)
        assert get_state(session_id) == {}


class TestConsoleLogging:
    def test_save_and_get_console_logs(self):
        session_id = "test_console_logs"

        try:
            save_console_log(session_id, {"type": "log", "text": "Hello"})
            save_console_log(session_id, {"type": "error", "text": "Oops"})

            logs = get_console_logs(session_id)
            assert len(logs) == 2
            assert logs[0]["text"] == "Hello"
            assert logs[1]["text"] == "Oops"
        finally:
            clear_logs(session_id)

    def test_console_log_limit(self):
        session_id = "test_console_limit"

        try:
            # Add more than 100 logs
            for i in range(110):
                save_console_log(session_id, {"type": "log", "text": f"Log {i}"})

            logs = get_console_logs(session_id)
            assert len(logs) == 100  # Should be capped at 100
        finally:
            clear_logs(session_id)


class TestNetworkLogging:
    def test_save_and_get_network_logs(self):
        session_id = "test_network_logs"

        try:
            logs = {
                "req1": {"method": "GET", "url": "http://example.com", "status": 200},
                "req2": {"method": "POST", "url": "http://example.com/api", "status": 201},
            }
            save_network_logs(session_id, logs)

            retrieved = get_network_logs(session_id)
            assert len(retrieved) == 2
            assert retrieved["req1"]["status"] == 200
        finally:
            clear_logs(session_id)


class TestProcessRunning:
    def test_current_process_is_running(self):
        import os
        assert is_process_running(os.getpid()) is True

    def test_invalid_pid_not_running(self):
        # Very high PID unlikely to exist
        assert is_process_running(999999999) is False


class TestPathValidation:
    def test_validate_path_in_sandbox_valid(self, tmp_path):
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        file_path = sandbox / "test.txt"
        file_path.write_text("hello")
        
        result = validate_path_in_sandbox(file_path, sandbox)
        assert result == file_path.resolve()

    def test_validate_path_in_sandbox_escapes(self, tmp_path):
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("secret")
        
        from agent_browser.utils import PathTraversalError
        with pytest.raises(PathTraversalError):
            validate_path_in_sandbox(outside, sandbox)

    def test_validate_path_default_root(self):
        # Path relative to CWD should be valid
        p = Path("README.md")
        result = validate_path(p)
        assert result == p.resolve()

    def test_validate_output_dir_valid(self, tmp_path):
        cwd = tmp_path / "project"
        cwd.mkdir()
        out = cwd / "screenshots"
        out.mkdir()
        
        result = validate_output_dir(out, cwd)
        assert result == out.resolve()

    def test_validate_output_dir_escapes(self, tmp_path):
        from agent_browser.utils import PathTraversalError
        cwd = tmp_path / "project"
        cwd.mkdir()
        out = tmp_path / "other_place"
        out.mkdir()
        
        with pytest.raises(PathTraversalError):
            validate_output_dir(out, cwd)
