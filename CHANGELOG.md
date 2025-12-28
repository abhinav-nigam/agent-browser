# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2025-12-28

### Added
- Feature Showcase in README with demo GIFs (Claude, Gemini, Interpreter).
- Adoption assets: Recipes, VS-Selenium comparison, and expanded Blog post.

### Fixed
- Path Traversal Security: Added sandboxing for all file operations (screenshots, uploads, output directories).
- README: Fixed encoding issues and character artifacts.
- Interactive mode: Added validation for empty JS eval strings.

## [0.1.2] - 2024-12-28

### Fixed
- Python 3.9 compatibility: fix remaining str | None syntax in interactive.py

## [0.1.1] - 2024-12-28

### Fixed
- Python 3.9 compatibility: use Union type syntax instead of | operator

## [0.1.0] - 2025-01-01

### Added
- Initial release
- Browser control commands (start, stop, status, reload, goto, back, forward)
- Screenshot capture with automatic resizing for AI vision models
- Interaction commands (click, fill, type, select, scroll, hover, focus, upload)
- Dialog handling (accept, dismiss)
- Assertion commands with PASS/FAIL output
- Data extraction commands (text, value, attr, count, eval, cookies, storage)
- Debugging commands (console, network, wait, wait_for)
- Multi-session support for concurrent browser instances
- Interactive mode for manual testing
- File-based IPC architecture for AI agent integration
- Cross-platform support (Windows, macOS, Linux)
