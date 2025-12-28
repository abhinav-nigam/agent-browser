# Agent Browser vs. Selenium and Playwright

Agent Browser aims to give agentic workflows the immediacy of a local tool with the ergonomics of a cloud API. Here is how it differs from Selenium and Playwright.

- **Simplified Setup (Managed Binaries):** Automates browser installation via Playwright; no manual driver downloads or version pinning required.
- **Local-First (no cloud API costs):** Runs entirely on the machine where the agent executes, avoiding per-run cloud charges and keeping data local by default.
- **File-based IPC (sandbox friendly):** Communicates through file-based inputs/outputs so sandboxed agents can interact without sockets or long-lived processes.
- **AI-Native features:** Supports AI-friendly behaviors such as automatic viewport resizing to match screenshots and simple pass/fail assertions to reduce prompt complexity.
