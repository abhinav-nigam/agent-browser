# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.7] - 2026-01-11

### Added
- **Screenshot quality modes** to prevent compression artifacts in video production:
  - `screenshot(quality="full")` - Original resolution, no compression (for Ken Burns videos)
  - `screenshot(quality="optimized")` - Auto-resize to 2000px max (default, for LLM debugging)
  - `full_page` parameter to choose between full page and viewport screenshots
- CLI: `screenshot full [name]` flag for full-quality screenshots
- Best practices in `check_environment()` for screenshot quality in video workflows

### Changed
- MCP screenshot tool now defaults to `quality="optimized"` with option for full quality
- CLI screenshot command supports both `viewport` and `full` flags in any order

## [0.2.6] - 2026-01-11

### Added
- **Voice modulation parameters** for ElevenLabs TTS to reduce robotic-sounding output:
  - `stability` (0.0-1.0): Lower values = more expressive speech. Default 0.4
  - `similarity_boost` (0.0-1.0): Voice clarity. Default 0.65
  - `style` (0.0-1.0): Expressiveness/emotion. Default 0.2
  - `use_speaker_boost` (bool): Enhance clarity. Default True
- New recommended voices for natural speech:
  - `H2JKG8QcEaH9iUMauArc` (Abhinav - warm, natural)
  - `qr9D67rNgxf5xNgv46nx` (Tarun - expressive)

### Changed
- ElevenLabs default settings optimized for less robotic output (stability=0.4, style=0.2)
- Updated all documentation and examples to use new voice recommendations and modulation

## [0.2.5] - 2026-01-10

### Changed
- **Breaking**: Removed slow post-production MCP tools that caused MCP timeouts: `merge_audio_video`, `add_background_music`, `convert_to_mp4`, `add_text_overlay`, `concatenate_videos`
- Agents should now use ffmpeg directly via shell commands for video processing (avoids MCP protocol-level timeouts)
- `check_environment()` now returns comprehensive `ffmpeg_examples` dict with copy-paste commands for all post-production tasks
- Updated workflow guide in `check_environment()` to recommend shell-based ffmpeg for Phase 3

### Added
- `ffmpeg_examples` in `check_environment()` output with 8 ready-to-use ffmpeg commands
- Updated best practices for shell-based video processing workflow

### Kept (fast utility tools)
- `check_environment()` - Environment check and ffmpeg command examples
- `get_video_duration()` - Quick video duration lookup
- `list_stock_music()` - Jamendo music search
- `download_stock_music()` - Music download

## [0.2.4] - 2026-01-09

### Fixed
- **Critical**: MCP timeout during video processing - ffmpeg operations now use async subprocess to keep event loop responsive
- Long-running `merge_audio_video`, `add_background_music`, `convert_to_mp4`, `add_text_overlay`, and `concatenate_videos` no longer block the MCP server

## [0.2.3] - 2026-01-09

### Added
- `convert_to_mp4` tool for converting video formats with configurable quality presets

### Fixed
- Auto-detect codec for smart fast mode in `merge_audio_video` (fixes compatibility issues)
- Increased ffmpeg timeout for longer video processing
- Fixed Playwright selector support in cinematic tools

### Changed
- Test suite performance improved by 56% (216s → 94s) via shared browser fixtures and local test pages

## [0.1.6] - 2025-12-29

### Fixed
- **Critical**: MCP server async deadlock - browser now uses lazy initialization within FastMCP's event loop context, fixing indefinite hangs on all tool calls
- MCP `_record_network` TypeError during browser shutdown when `request.failure()` returns None

### Added
- **16 new MCP tools** expanding from 20 to 36 total tools:
  - `wait_for` - wait for selector to appear (critical for SPAs)
  - `wait_for_text` - wait for specific text to appear
  - `text` - get element's text content
  - `value` - get input field value
  - `attr` - get element attribute
  - `count` - count matching elements
  - `press` - press keyboard keys (Enter, Tab, Escape, etc.)
  - `reload` - reload current page
  - `viewport` - set viewport size
  - `assert_visible` - check element visibility [PASS/FAIL]
  - `assert_text` - check element contains text [PASS/FAIL]
  - `clear` - clear localStorage and sessionStorage
  - `dialog` - handle JavaScript alerts/confirms/prompts
  - `wait_for_url` - wait for URL to contain pattern (useful for navigation)
  - `wait_for_load_state` - wait for load/domcontentloaded/networkidle
  - `assert_url` - check if URL contains pattern [PASS/FAIL]
- Claude Code CLI configuration instructions in README
- `configure()` method on BrowserServer for setting options before run
- `validate_path_in_sandbox()` and `validate_output_dir()` utility functions
- Console log limiting (max 200 entries) to prevent memory growth
- Comprehensive MCP security documentation

### Changed
- MCP server now starts browser on first tool call (lazy init) instead of pre-starting
- Exported `BrowserServer`, `URLValidator`, and utility functions from package root

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
