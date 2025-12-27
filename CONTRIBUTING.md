# Contributing to agent-browser

Thank you for your interest in contributing to agent-browser!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/abhinav-nigam/agent-browser.git
   cd agent-browser
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   ```

3. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   playwright install chromium
   ```

4. Run tests:
   ```bash
   pytest
   ```

## Code Style

- Use type hints for all function signatures
- Follow PEP 8 style guidelines
- Keep functions focused and well-documented
- Write docstrings for public APIs

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Adding New Commands

To add a new browser command:

1. Add the command handler in `driver.py` within `process_command()`
2. Follow the existing pattern:
   ```python
   if cmd == "your_command":
       # Parse arguments from parts or cmd_text
       # Execute the action
       return "Result message"
   ```
3. Add documentation to README.md
4. Add a test case

## Reporting Issues

When reporting issues, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Any error messages

## License

By contributing, you agree that your contributions will be licensed under the GNU General Public License v3.0.
