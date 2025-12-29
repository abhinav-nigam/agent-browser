"""Tests for BrowserDriver class."""


from agent_browser.driver import BrowserDriver, HELP_TEXT


class TestBrowserDriverInit:
    def test_default_session_id(self):
        driver = BrowserDriver()
        assert driver.session_id == "default"

    def test_custom_session_id(self):
        driver = BrowserDriver(session_id="my_session")
        assert driver.session_id == "my_session"

    def test_session_id_sanitized(self):
        driver = BrowserDriver(session_id="path/to/session")
        assert "/" not in driver.session_id

    def test_default_output_dir(self):
        driver = BrowserDriver()
        assert "screenshots" in str(driver.output_dir)

    def test_custom_output_dir(self, tmp_path):
        driver = BrowserDriver(output_dir=tmp_path / "custom")
        assert driver.output_dir == tmp_path / "custom"


class TestHelpText:
    def test_help_text_not_empty(self):
        assert len(HELP_TEXT) > 100

    def test_help_contains_commands(self):
        assert "click" in HELP_TEXT
        assert "screenshot" in HELP_TEXT
        assert "assert_visible" in HELP_TEXT

    def test_help_contains_sections(self):
        assert "BROWSER CONTROL" in HELP_TEXT
        assert "SCREENSHOTS" in HELP_TEXT
        assert "INTERACTIONS" in HELP_TEXT
        assert "ASSERTIONS" in HELP_TEXT


class TestSendCommandWithoutBrowser:
    def test_send_command_no_browser(self):
        driver = BrowserDriver(session_id="test_no_browser")
        result = driver.send_command("screenshot test")
        assert "Error" in result or "not running" in result.lower()


class TestStatus:
    def test_status_no_browser(self, capsys):
        driver = BrowserDriver(session_id="test_status_no_browser")
        result = driver.status()
        assert result is False
        captured = capsys.readouterr()
        assert "NOT RUNNING" in captured.out
