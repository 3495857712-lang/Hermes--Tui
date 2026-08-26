# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-15

### Added

- Initial release of Hermes TUI
- Terminal user interface built with [Textual](https://textual.textualize.io/)
- Multi-provider LLM support:
  - OpenAI (GPT-4o, GPT-4o-mini, o1)
  - Ollama (local models)
  - OpenRouter (aggregated models)
  - DeepSeek (DeepSeek-V3, DeepSeek-R1)
- Three-tier memory architecture:
  - Immediate layer (user profile, core rules, secrets)
  - Near-mid term layer (project snapshots, decisions, todos)
  - Long-term layer (SQLite with FTS5 full-text search)
- Skill system with progressive loading:
  - `SKILL.md` manifest format with YAML frontmatter
  - Three-level progressive loading (main file → references → scripts)
  - Automatic skill matching based on user intent
- Tool system with decorator-based registration:
  - `@registry.register` decorator for custom tools
  - Automatic JSON Schema generation from type hints
  - Built-in tools: web search, file read/write, bash execution
- Configuration system:
  - YAML configuration with environment variable overrides
  - Multi-profile support
  - Secure API key storage via environment variables or `.env`
- Agent loop with:
  - Streaming responses
  - Tool call orchestration
  - Context window management
  - Retry logic with exponential backoff (tenacity)
- Chat interface features:
  - Markdown rendering with syntax highlighting
  - Multi-line input with vim-style keybindings
  - Command palette (`Ctrl+P`)
  - Message history navigation
  - Token usage display
- Database layer:
  - SQLite for persistent storage
  - FTS5 full-text search for memory retrieval
  - Automatic migrations
- Docker support with multi-stage build
- Comprehensive documentation:
  - Installation guide
  - Configuration reference
  - Skill development guide
  - Tool development guide
  - Architecture overview
  - Usage examples
  - FAQ
- Development tooling:
  - Ruff for linting and formatting
  - Mypy strict type checking
  - Pytest with asyncio support and coverage
  - Pre-commit hooks
  - GitHub Actions CI/CD
- Cross-platform support: Linux, macOS, Windows

### Changed

- N/A (initial release)

### Removed

- N/A (initial release)

[0.1.0]: https://github.com/hermes-tui/hermes-tui/releases/tag/v0.1.0
