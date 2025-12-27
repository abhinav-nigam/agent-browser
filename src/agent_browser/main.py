"""Command-line interface for the agent-browser package."""

import argparse
from typing import Optional, Sequence

from .driver import BrowserDriver
from .interactive import InteractiveRunner
from .utils import configure_windows_console

DEFAULT_URL = "http://localhost:8080"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-browser",
        description="Control a Playwright browser via CLI or interactive runner.",
    )
    parser.add_argument(
        "--session",
        default="default",
        help="Session identifier used for IPC files (default: default).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to store screenshots (used when starting a session).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start the headless driver (blocks).")
    start_parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help="Initial URL to open.",
    )
    start_parser.add_argument(
        "--visible",
        action="store_true",
        help="Launch browser in headed mode instead of headless.",
    )

    interact_parser = subparsers.add_parser("interact", help="Start the interactive runner.")
    interact_parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help="Initial URL to open.",
    )
    interact_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the interactive runner in headless mode.",
    )

    subparsers.add_parser("status", help="Check if the driver is running.")
    subparsers.add_parser("stop", help="Stop the running driver.")

    cmd_parser = subparsers.add_parser("cmd", help="Send a command to the running driver.")
    cmd_parser.add_argument(
        "cmd_args",
        nargs=argparse.REMAINDER,
        help="Command string to forward (e.g., screenshot home).",
    )
    cmd_parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Seconds to wait for a response (defaults to IPC timeout).",
    )

    return parser


def run_start(args: argparse.Namespace) -> None:
    driver = BrowserDriver(session_id=args.session, output_dir=args.output_dir)
    driver.start(args.url, headless=not args.visible)


def run_interact(args: argparse.Namespace) -> None:
    runner_kwargs = {
        "session_id": args.session,
        "output_dir": args.output_dir,
        "headless": args.headless,
    }
    try:
        runner = InteractiveRunner(args.url, **runner_kwargs)
    except NotImplementedError as exc:
        raise SystemExit(str(exc)) from exc

    try:
        if hasattr(runner, "run"):
            runner.run()
        elif hasattr(runner, "start"):
            runner.start()
        else:
            raise RuntimeError("InteractiveRunner must expose a run() or start() method")
    except NotImplementedError as exc:
        raise SystemExit(str(exc)) from exc


def run_status(args: argparse.Namespace) -> int:
    driver = BrowserDriver(session_id=args.session, output_dir=args.output_dir)
    return 0 if driver.status() else 1


def run_stop(args: argparse.Namespace) -> None:
    driver = BrowserDriver(session_id=args.session, output_dir=args.output_dir)
    print(driver.stop())


def run_cmd(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    cmd_text = " ".join(args.cmd_args).strip()
    if not cmd_text:
        parser.error("cmd requires a command string (e.g., agent-browser cmd screenshot home)")

    driver = BrowserDriver(session_id=args.session, output_dir=args.output_dir)
    result = driver.send_command(cmd_text, timeout=args.timeout)
    print(result)


def main(argv: Optional[Sequence[str]] = None) -> int:
    configure_windows_console()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "start":
        run_start(args)
        return 0
    if args.command == "interact":
        run_interact(args)
        return 0
    if args.command == "status":
        return run_status(args)
    if args.command == "stop":
        run_stop(args)
        return 0
    if args.command == "cmd":
        run_cmd(args, parser)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
