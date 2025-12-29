"""
Browser driver logic for agent-browser.

Encapsulates browser automation and IPC handling in a class-based design.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union

from .utils import (
    IPC_TIMEOUT,
    DEFAULT_TIMEOUT,
    WAIT_FOR_TIMEOUT,
    PathTraversalError,
    add_network_request,
    clear_logs,
    clear_state,
    configure_windows_console,
    format_assertion_result,
    get_browser_pid,
    get_command_file,
    get_console_log_file,
    get_console_logs,
    get_network_log_file,
    get_network_logs,
    get_pid_file,
    get_result_file,
    sanitize_filename,
    get_state,
    get_state_file,
    is_process_running,
    resize_screenshot_if_needed,
    save_browser_pid,
    save_console_log,
    save_network_logs,
    save_state,
    validate_path,
)

HELP_TEXT = """
agent-browser - Browser automation for AI agents

BROWSER CONTROL
  start <url> [--visible]   Start browser (blocks - run in separate terminal)
  stop                      Close browser
  status                    Check if browser is running
  reload                    Reload page
  goto <url>                Navigate to URL
  back                      Navigate back
  forward                   Navigate back
  url                       Print current URL
  viewport <w> <h>          Set viewport size

SCREENSHOTS
  screenshot [name]         Full-page screenshot
  screenshot viewport [name] Viewport only (faster)
  ss [name]                 Alias for screenshot

INTERACTIONS
  click <selector>          Click element
  click_nth <selector> <n>  Click nth element (0-indexed)
  fill <selector> <text>    Fill input field
  type <selector> <text>    Type with key events
  select <selector> <value> Select dropdown option
  press <key>               Press keyboard key (Enter, Tab, etc.)
  scroll <direction>        Scroll: up/down/top/bottom/left/right
  hover <selector>          Hover over element
  focus <selector>          Focus element
  upload <selector> <path>  Upload file to input
  dialog <action> [text]    Handle dialog: accept, dismiss
  clear                     Clear localStorage/sessionStorage

ASSERTIONS (return [PASS]/[FAIL])
  assert_visible <selector> Element is visible
  assert_hidden <selector>  Element is hidden
  assert_text <sel> <text>  Element contains text
  assert_text_exact <s> <t> Text matches exactly
  assert_value <sel> <val>  Input value matches
  assert_checked <selector> Checkbox is checked
  assert_url <pattern>      URL contains pattern

DATA EXTRACTION
  text <selector>           Get text content
  value <selector>          Get input value
  attr <selector> <attr>    Get attribute value
  count <selector>          Count matching elements
  eval <javascript>         Execute JS, return result
  cookies                   Get all cookies (JSON)
  storage                   Get localStorage (JSON)

DEBUGGING
  console                   View JS console logs
  network                   View network requests (with timing)
  network_failed            View failed requests only
  clear_logs                Clear console/network logs
  wait <ms>                 Wait milliseconds
  wait_for <selector> [ms]  Wait for element (default 10s)
  wait_for_text <text>      Wait for text to appear
  help                      Show this help
"""


class BrowserDriver:
    """Encapsulates Playwright browser automation with IPC command handling."""

    def __init__(self, session_id: str = "default", output_dir: Optional[Union[str, Path]] = None) -> None:
        self.session_id = sanitize_filename(session_id or "default")
        output_dir_path = Path(output_dir) if output_dir else Path("./screenshots")
        # For output_dir, we trust explicitly provided paths (absolute or relative)
        # Sandbox validation is only for runtime file operations, not initial config
        self.output_dir = output_dir_path.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.command_file = get_command_file(self.session_id)
        self.result_file = get_result_file(self.session_id)
        self.state_file = get_state_file(self.session_id)
        self.console_log_file = get_console_log_file(self.session_id)
        self.network_log_file = get_network_log_file(self.session_id)
        self.pid_file = get_pid_file(self.session_id)

        self._command_seq = 0

    def _update_state_url(self, url: str) -> None:
        state = get_state(self.session_id)
        state["url"] = url
        state["last_update"] = datetime.now().isoformat()
        save_state(self.session_id, state)

    def _write_result(self, result: str, seq: int) -> None:
        self.result_file.write_text(
            json.dumps(
                {"result": result, "seq": seq, "timestamp": datetime.now().isoformat()}
            )
        )

    def process_command(self, page: Any, cmd_text: str, step: int, pending_dialog: Optional[List[Any]] = None) -> str:
        """
        Process a single command and return the result.

        Args:
            page: Playwright page object
            cmd_text: Full command text
            step: Current step number for screenshot naming
            pending_dialog: List containing pending dialog (mutable for closure)

        Returns:
            Result string (or "__STOP__" to signal shutdown)
        """
        parts = cmd_text.split(maxsplit=2)
        cmd = parts[0].lower()

        try:
            # BROWSER CONTROL
            if cmd == "stop":
                return "__STOP__"
            if cmd == "ping":
                return f"PONG:{page.url}"
            if cmd == "reload":
                page.reload(wait_until="networkidle")
                return f"Reloaded. URL: {page.url}"
            if cmd == "goto":
                new_url = cmd_text[5:].strip() if len(cmd_text) > 5 else ""
                if not new_url:
                    return "Error: URL required"
                page.goto(new_url, wait_until="networkidle")
                return f"Navigated to {page.url}"
            if cmd == "back":
                page.go_back(wait_until="networkidle")
                return f"Navigated back. URL: {page.url}"
            if cmd == "forward":
                page.go_forward(wait_until="networkidle")
                return f"Navigated forward. URL: {page.url}"
            if cmd == "viewport":
                if len(parts) < 3:
                    return "Error: Usage: viewport <width> <height>"
                try:
                    width = int(parts[1])
                    height = int(parts[2])
                except ValueError:
                    return "Error: Width and height must be integers"
                page.set_viewport_size({"width": width, "height": height})
                return f"Viewport set to {width}x{height}"
            if cmd == "url":
                return page.url

            # SCREENSHOTS
            if cmd in ("screenshot", "ss"):
                viewport_only = len(parts) > 1 and parts[1].lower() == "viewport"
                if viewport_only:
                    name = parts[2] if len(parts) > 2 else f"step_{step:02d}"
                else:
                    name = parts[1] if len(parts) > 1 else f"step_{step:02d}"
                safe_name = sanitize_filename(name)
                filepath = self.output_dir / f"{safe_name}.png"
                page.screenshot(path=str(filepath), full_page=not viewport_only)
                resize_status = resize_screenshot_if_needed(filepath)
                return f"Screenshot: {filepath} [{resize_status}]"

            # INTERACTION
            if cmd == "click":
                selector = cmd_text[6:].strip()
                if not selector:
                    return "Error: Selector required"
                page.click(selector, timeout=DEFAULT_TIMEOUT)
                return f"Clicked: {selector}"

            if cmd == "click_nth":
                rest = cmd_text[len("click_nth") :].strip()
                if not rest:
                    return "Error: Usage: click_nth <selector> <index>"
                try:
                    selector, index_str = rest.rsplit(maxsplit=1)
                except ValueError:
                    return "Error: Usage: click_nth <selector> <index>"
                try:
                    index = int(index_str)
                except ValueError:
                    return f"Error: Invalid index '{index_str}'"
                elements = page.locator(selector)
                count = elements.count()
                if index >= count:
                    return f"Error: Index {index} out of range (found {count} elements)"
                elements.nth(index).click(timeout=DEFAULT_TIMEOUT)
                return f"Clicked: {selector} [index={index}]"

            if cmd == "fill":
                if len(parts) < 2:
                    return "Error: Usage: fill <selector> <text>"
                selector = parts[1]
                text = parts[2] if len(parts) > 2 else ""
                page.fill(selector, text, timeout=DEFAULT_TIMEOUT)
                return f"Filled: {selector} with '{text}'"

            if cmd == "type":
                if len(parts) < 2:
                    return "Error: Usage: type <selector> <text>"
                selector = parts[1]
                text = parts[2] if len(parts) > 2 else ""
                page.type(selector, text, timeout=DEFAULT_TIMEOUT)
                return f"Typed: '{text}' into {selector}"

            if cmd == "select":
                if len(parts) < 3:
                    return "Error: Usage: select <selector> <value>"
                selector = parts[1]
                value = parts[2]
                page.select_option(selector, value, timeout=DEFAULT_TIMEOUT)
                return f"Selected: '{value}' in {selector}"

            if cmd == "press":
                key = parts[1] if len(parts) > 1 else "Enter"
                page.keyboard.press(key)
                return f"Pressed: {key}"

            if cmd == "scroll":
                direction = parts[1].lower() if len(parts) > 1 else "down"
                scroll_map = {
                    "top": "window.scrollTo(0, 0)",
                    "bottom": "window.scrollTo(0, document.body.scrollHeight)",
                    "up": "window.scrollBy(0, -500)",
                    "down": "window.scrollBy(0, 500)",
                    "left": "window.scrollBy(-500, 0)",
                    "right": "window.scrollBy(500, 0)",
                }
                if direction not in scroll_map:
                    return (
                        f"Error: Invalid direction '{direction}'. "
                        "Use: top/bottom/up/down/left/right"
                    )
                page.evaluate(scroll_map[direction])
                return f"Scrolled: {direction}"

            if cmd == "hover":
                selector = cmd_text[6:].strip()
                if not selector:
                    return "Error: Selector required"
                page.hover(selector, timeout=DEFAULT_TIMEOUT)
                return f"Hovering: {selector}"

            if cmd == "focus":
                selector = cmd_text[6:].strip()
                if not selector:
                    return "Error: Selector required"
                page.focus(selector, timeout=DEFAULT_TIMEOUT)
                return f"Focused: {selector}"

            if cmd == "upload":
                if len(parts) < 3:
                    return "Error: Usage: upload <selector> <file_path>"
                selector = parts[1]
                file_path = parts[2]
                # Validate file path is within CWD to prevent path traversal
                try:
                    validated_path = validate_path(file_path)
                except PathTraversalError:
                    return f"Error: Path '{file_path}' escapes current working directory"
                if not validated_path.exists():
                    return f"Error: File not found: {file_path}"
                page.set_input_files(selector, str(validated_path), timeout=DEFAULT_TIMEOUT)
                return f"Uploaded: {validated_path} to {selector}"

            if cmd == "dialog":
                if pending_dialog is None or pending_dialog[0] is None:
                    return "No pending dialog"
                dialog = pending_dialog[0]
                action = parts[1].lower() if len(parts) > 1 else "accept"
                if action == "accept":
                    prompt_text = parts[2] if len(parts) > 2 else None
                    if prompt_text:
                        dialog.accept(prompt_text)
                    else:
                        dialog.accept()
                    pending_dialog[0] = None
                    return "Dialog accepted"
                if action == "dismiss":
                    dialog.dismiss()
                    pending_dialog[0] = None
                    return "Dialog dismissed"
                return f"Error: Unknown action '{action}'. Use: accept, dismiss"

            # ASSERTIONS
            if cmd == "assert_visible":
                selector = cmd_text[14:].strip()
                if not selector:
                    return format_assertion_result(False, "Selector required")
                try:
                    page.wait_for_selector(selector, state="visible", timeout=DEFAULT_TIMEOUT)
                    return format_assertion_result(True, f"Element visible: {selector}")
                except Exception:
                    return format_assertion_result(False, f"Element NOT visible: {selector}")

            if cmd == "assert_hidden":
                selector = cmd_text[13:].strip()
                if not selector:
                    return format_assertion_result(False, "Selector required")
                try:
                    page.wait_for_selector(selector, state="hidden", timeout=DEFAULT_TIMEOUT)
                    return format_assertion_result(True, f"Element hidden: {selector}")
                except Exception:
                    return format_assertion_result(False, f"Element NOT hidden (still visible): {selector}")

            if cmd == "assert_text":
                rest = cmd_text[12:].strip()
                space_idx = rest.find(" ")
                if space_idx == -1:
                    return format_assertion_result(False, "Usage: assert_text <selector> <text>")
                selector = rest[:space_idx]
                expected = rest[space_idx + 1 :]
                try:
                    actual = page.text_content(selector, timeout=DEFAULT_TIMEOUT) or ""
                    if expected in actual:
                        return format_assertion_result(True, f"Text found: '{expected}' in {selector}")
                    return format_assertion_result(
                        False, f"Text NOT found: '{expected}' in {selector}. Actual: '{actual[:100]}'")
                except Exception as exc:
                    return format_assertion_result(False, f"Error getting text: {exc}")

            if cmd == "assert_text_exact":
                rest = cmd_text[18:].strip()
                space_idx = rest.find(" ")
                if space_idx == -1:
                    return format_assertion_result(False, "Usage: assert_text_exact <selector> <text>")
                selector = rest[:space_idx]
                expected = rest[space_idx + 1 :]
                try:
                    actual = page.text_content(selector, timeout=DEFAULT_TIMEOUT) or ""
                    if actual.strip() == expected.strip():
                        return format_assertion_result(True, f"Text matches exactly: {selector}")
                    return format_assertion_result(
                        False, f"Text mismatch. Expected: '{expected}', Actual: '{actual[:100]}'")
                except Exception as exc:
                    return format_assertion_result(False, f"Error getting text: {exc}")

            if cmd == "assert_value":
                rest = cmd_text[13:].strip()
                space_idx = rest.find(" ")
                if space_idx == -1:
                    return format_assertion_result(False, "Usage: assert_value <selector> <value>")
                selector = rest[:space_idx]
                expected = rest[space_idx + 1 :]
                try:
                    actual = page.input_value(selector, timeout=DEFAULT_TIMEOUT)
                    if actual == expected:
                        return format_assertion_result(True, f"Value matches: {selector}")
                    return format_assertion_result(
                        False, f"Value mismatch. Expected: '{expected}', Actual: '{actual}'")
                except Exception as exc:
                    return format_assertion_result(False, f"Error getting value: {exc}")

            if cmd == "assert_checked":
                selector = cmd_text[14:].strip()
                if not selector:
                    return format_assertion_result(False, "Selector required")
                try:
                    is_checked = page.is_checked(selector, timeout=DEFAULT_TIMEOUT)
                    if is_checked:
                        return format_assertion_result(True, f"Element is checked: {selector}")
                    return format_assertion_result(False, f"Element NOT checked: {selector}")
                except Exception as exc:
                    return format_assertion_result(False, f"Error checking state: {exc}")

            if cmd == "assert_url":
                pattern = cmd_text[11:].strip()
                if not pattern:
                    return format_assertion_result(False, "URL pattern required")
                current_url = page.url
                if pattern in current_url:
                    return format_assertion_result(True, f"URL contains '{pattern}': {current_url}")
                return format_assertion_result(False, f"URL does NOT contain '{pattern}': {current_url}")

            # DATA EXTRACTION
            if cmd == "text":
                selector = cmd_text[5:].strip()
                if not selector:
                    return "Error: Selector required"
                text = page.text_content(selector, timeout=DEFAULT_TIMEOUT)
                return text if text else "(empty)"

            if cmd == "value":
                selector = cmd_text[6:].strip()
                if not selector:
                    return "Error: Selector required"
                value = page.input_value(selector, timeout=DEFAULT_TIMEOUT)
                return value if value else "(empty)"

            if cmd == "attr":
                if len(parts) < 3:
                    return "Error: Usage: attr <selector> <attribute>"
                selector = parts[1]
                attribute = parts[2]
                value = page.get_attribute(selector, attribute, timeout=DEFAULT_TIMEOUT)
                return value if value else "(null)"

            if cmd == "count":
                selector = cmd_text[6:].strip()
                if not selector:
                    return "Error: Selector required"
                count = page.locator(selector).count()
                return str(count)

            if cmd == "eval":
                js = cmd_text[5:].strip()
                if not js:
                    return "Error: JavaScript code required"
                result = page.evaluate(js)
                return str(result)

            if cmd == "cookies":
                cookies = page.context.cookies()
                return json.dumps(cookies, indent=2)

            if cmd == "storage":
                storage = page.evaluate("JSON.stringify(localStorage)")
                return storage if storage else "{}"

            # DEBUGGING
            if cmd == "console":
                logs = get_console_logs(self.session_id)
                if not logs:
                    return "No console logs"
                output = []
                for log in logs[-20:]:
                    log_type = log.get("type", "log").upper()
                    text = log.get("text", "")[:200]
                    output.append(f"[{log_type}] {text}")
                return "\n".join(output)

            if cmd == "network":
                net_logs = get_network_logs(self.session_id)
                if not net_logs:
                    return "No network requests logged"
                output = []
                sorted_logs = sorted(net_logs.values(), key=lambda x: x.get("start_time", ""), reverse=True)[:20]
                for log in reversed(sorted_logs):
                    method = log.get("method", "?")
                    url = log.get("url", "")
                    short_url = url[:70] + "..." if len(url) > 70 else url
                    status = log.get("status", "pending")
                    duration = log.get("duration_ms", "")
                    if duration:
                        output.append(f"{method} {status} {duration}ms {short_url}")
                    else:
                        output.append(f"{method} {status} {short_url}")
                return "\n".join(output)

            if cmd == "network_failed":
                net_logs_failed = get_network_logs(self.session_id)
                failed = [log for log in net_logs_failed.values() if log.get("status") == "failed"]
                if not failed:
                    return "No failed requests"
                output = []
                for log in failed:
                    method = log.get("method", "?")
                    url = log.get("url", "")[:80]
                    failure = log.get("failure", "unknown")
                    output.append(f"{method} {url}\n  Failure: {failure}")
                return "\n".join(output)

            if cmd == "clear_logs":
                clear_logs(self.session_id)
                return "Console and network logs cleared"

            if cmd == "wait":
                ms = int(parts[1]) if len(parts) > 1 else 1000
                page.wait_for_timeout(ms)
                return f"Waited {ms}ms"

            if cmd == "wait_for":
                rest = cmd_text[9:].strip()
                parts_wf = rest.split()
                if not parts_wf:
                    return "Error: Selector required"
                selector = parts_wf[0]
                timeout_ms = WAIT_FOR_TIMEOUT
                if len(parts_wf) > 1:
                    try:
                        timeout_ms = int(parts_wf[1])
                    except ValueError:
                        pass
                try:
                    page.wait_for_selector(selector, timeout=timeout_ms)
                    return f"Element appeared: {selector}"
                except Exception:
                    return f"Timeout waiting for: {selector} (waited {timeout_ms}ms)"

            if cmd == "wait_for_text":
                text = cmd_text[14:].strip()
                if not text:
                    return "Error: Text required"
                try:
                    page.wait_for_selector(f"text={text}", timeout=WAIT_FOR_TIMEOUT)
                    return f"Text appeared: '{text}'"
                except Exception:
                    return f"Timeout waiting for text: '{text}'"

            if cmd == "help":
                return HELP_TEXT

            if cmd == "clear":
                page.evaluate("localStorage.clear(); sessionStorage.clear();")
                return "Cleared localStorage and sessionStorage"

            return f"Unknown command: '{cmd}'. Use 'help' for available commands."

        except Exception as exc:
            return f"Error: {exc}"

    def start(self, url: str, headless: bool = True) -> None:
        """
        Start browser session and enter command processing loop.

        The call blocks while the browser is running; commands are processed
        via IPC files scoped by session_id.
        """
        from playwright.sync_api import sync_playwright

        self._command_seq = 0
        clear_state(self.session_id)
        clear_logs(self.session_id)
        save_browser_pid(self.session_id)

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=headless, slow_mo=0 if headless else 50)
        context = browser.new_context(viewport={"width": 1280, "height": 900}, storage_state=None)
        page = context.new_page()

        pending_dialog: List[Optional[Any]] = [None]

        def handle_dialog(dialog: Any) -> None:
            pending_dialog[0] = dialog
            print(f"[DIALOG] {dialog.type}: {dialog.message}")

        page.on("dialog", handle_dialog)

        def handle_console(msg: Any) -> None:
            save_console_log(
                self.session_id,
                {
                    "type": msg.type,
                    "text": msg.text,
                    "timestamp": datetime.now().isoformat(),
                    "location": str(msg.location) if msg.location else None,
                },
            )

        page.on("console", handle_console)

        def handle_request(request: Any) -> None:
            request_id = str(id(request))
            add_network_request(
                self.session_id,
                request_id,
                {"method": request.method, "url": request.url, "start_time": datetime.now().isoformat(), "status": "pending"},
            )
            request._tracking_id = request_id

        def handle_response(response: Any) -> None:
            request = response.request
            request_id = getattr(request, "_tracking_id", None)
            if request_id:
                end_time = datetime.now()
                logs = get_network_logs(self.session_id)
                if request_id in logs:
                    start_time = logs[request_id].get("start_time", "")
                    try:
                        start = datetime.fromisoformat(start_time)
                        duration_ms = int((end_time - start).total_seconds() * 1000)
                    except Exception:
                        duration_ms = 0
                    logs[request_id].update(
                        {
                            "status": response.status,
                            "status_text": response.status_text,
                            "end_time": end_time.isoformat(),
                            "duration_ms": duration_ms,
                        }
                    )
                    save_network_logs(self.session_id, logs)

        def handle_request_failed(request: Any) -> None:
            request_id = getattr(request, "_tracking_id", str(id(request)))
            failure_reason = request.failure if request.failure else "unknown"
            add_network_request(
                self.session_id,
                request_id,
                {
                    "method": request.method,
                    "url": request.url,
                    "status": "failed",
                    "failure": failure_reason,
                    "end_time": datetime.now().isoformat(),
                },
            )

        page.on("request", handle_request)
        page.on("response", handle_response)
        page.on("requestfailed", handle_request_failed)

        page.goto(url, wait_until="networkidle")

        mode = "headless" if headless else "visible"
        print(f"Browser started ({mode}) at {url}")
        print(f"Current URL: {page.url}")
        print(f"PID: {os.getpid()}")

        save_state(
            self.session_id,
            {
                "running": True,
                "url": page.url,
                "start_time": datetime.now().isoformat(),
                "last_update": datetime.now().isoformat(),
                "mode": mode,
                "pid": os.getpid(),
            },
        )

        screenshot_path = self.output_dir / f"{sanitize_filename('step_00_start')}.png"
        page.screenshot(path=str(screenshot_path), full_page=False)
        resize_status = resize_screenshot_if_needed(screenshot_path)
        print(f"Screenshot: {screenshot_path} [{resize_status}]")

        print("\nBrowser ready. Listening for commands...")
        step = 1
        last_seq = 0

        try:
            while True:
                try:
                    if self.command_file.exists():
                        try:
                            cmd_data = json.loads(self.command_file.read_text())
                            cmd_text = cmd_data.get("cmd", "").strip()
                            cmd_seq = cmd_data.get("seq", last_seq + 1)
                        except (json.JSONDecodeError, KeyError):
                            cmd_text = self.command_file.read_text().strip()
                            cmd_seq = last_seq + 1

                        try:
                            self.command_file.unlink()
                        except OSError:
                            pass

                        if not cmd_text:
                            continue

                        try:
                            result = self.process_command(page, cmd_text, step, pending_dialog)

                            if result == "__STOP__":
                                self._write_result("Browser stopped", cmd_seq)
                                break

                            if cmd_text.lower().startswith(("goto", "reload", "back", "forward")):
                                self._update_state_url(page.url)

                            if result.startswith("Screenshot:"):
                                step += 1

                            self._write_result(result, cmd_seq)
                            last_seq = cmd_seq
                            print(f"[CMD] {cmd_text[:50]}{'...' if len(cmd_text) > 50 else ''}")
                            print(f"[OUT] {result[:100]}{'...' if len(result) > 100 else ''}")
                        except Exception as exc:
                            error_msg = f"Error: {exc}"
                            self._write_result(error_msg, cmd_seq)
                            print(f"[ERR] {error_msg}")

                    page.wait_for_timeout(100)

                except KeyboardInterrupt:
                    print("\nInterrupted, closing browser...")
                    break
                except Exception as exc:
                    print(f"Error in main loop: {exc}")
                    continue
        finally:
            context.close()
            browser.close()
            pw.stop()
            clear_state(self.session_id)
            print("Browser closed.")

    def send_command(self, cmd: str, timeout: Optional[int] = None) -> str:
        """
        Send a command to the running browser and wait for result.

        Args:
            cmd: Command string to send
            timeout: Maximum seconds to wait for result (default: IPC_TIMEOUT)
        """
        if timeout is None:
            timeout = IPC_TIMEOUT

        state = get_state(self.session_id)
        if not state.get("running"):
            return "Error: Browser not running. Use 'start <url>' first."

        pid = state.get("pid") or get_browser_pid(self.session_id)
        if pid and not is_process_running(pid):
            clear_state(self.session_id)
            return "Error: Browser process has died. Use 'start <url>' to restart."

        self._command_seq += 1
        seq = self._command_seq

        if self.result_file.exists():
            try:
                self.result_file.unlink()
            except OSError:
                pass

        cmd_data = json.dumps({"cmd": cmd, "seq": seq})
        self.command_file.write_text(cmd_data)

        for _ in range(timeout * 10):
            if self.result_file.exists():
                try:
                    result_data = json.loads(self.result_file.read_text())
                    result_seq = result_data.get("seq", 0)
                    result = result_data.get("result", "")
                    if result_seq == seq:
                        try:
                            self.result_file.unlink()
                        except OSError:
                            pass
                        return result
                except (json.JSONDecodeError, OSError):
                    pass
            time.sleep(0.1)

        return "Timeout waiting for result. Browser may have crashed - check 'status'."

    def status(self) -> bool:
        """
        Check if browser is running and print status.

        Returns:
            True if running, False otherwise.
        """
        state = get_state(self.session_id)
        if not state.get("running"):
            print("Browser: NOT RUNNING")
            print("\nTo start: agent-browser start <url>")
            return False

        pid = state.get("pid") or get_browser_pid(self.session_id)
        if pid and not is_process_running(pid):
            print("Browser: CRASHED (process not found)")
            print(f"Last known PID: {pid}")
            clear_state(self.session_id)
            print("\nTo restart: agent-browser start <url>")
            return False

        print(f"Browser: CHECKING (PID: {pid})...")
        result = self.send_command("ping", timeout=3)

        if result.startswith("PONG:"):
            current_url = result[5:]
            print(f"Browser: RUNNING ({state.get('mode', 'unknown')} mode)")
            print(f"Since: {state.get('start_time', 'unknown')}")
            print(f"Current URL: {current_url}")
            print(f"Last state update: {state.get('last_update', 'unknown')}")
            print("\nLog files:")
            print(f"  Console: {self.console_log_file}")
            print(f"  Network: {self.network_log_file}")
            print(f"  Screenshots: {self.output_dir}")
            return True

        print("Browser: NOT RESPONDING")
        print(f"PID {pid} exists but browser is not accepting commands")
        print(f"Response: {result}")
        print("\nTry 'stop' then 'start <url>' to restart")
        return False

    def stop(self) -> str:
        return self.send_command("stop")


def main() -> None:
    """Backward-compatible entry point for direct execution."""
    configure_windows_console()
    driver = BrowserDriver()
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1].lower()
    if cmd == "status":
        driver.status()
    elif cmd == "start":
        args = [a for a in sys.argv[2:] if not a.startswith("--")]
        headless = "--visible" not in sys.argv
        url = args[0] if args else "http://localhost:8080"
        driver.start(url, headless=headless)
    else:
        result = driver.send_command(" ".join(sys.argv[1:]))
        print(result)


if __name__ == "__main__":
    main()