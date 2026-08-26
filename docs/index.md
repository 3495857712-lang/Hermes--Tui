# Hermes TUI Documentation

Welcome to the Hermes TUI documentation!

Hermes TUI is a terminal-based AI agent interface built with [Textual](https://textual.textualize.io/).
It connects to any OpenAI-compatible API (including local Ollama) and provides a rich
TUI experience with streaming, memory, skills, and tool use.

## Quick Links

- [Installation](installation.md) — Set up Hermes TUI on your machine
- [Configuration](configuration.md) — All configuration options explained
- [Architecture](architecture.md) — How the components fit together
- [Skills](skills.md) — Create and use skills
- [Memory](memory.md) — How the memory system works
- [Tools](tools.md) — Build custom tools
- [Examples](examples.md) — Usage examples
- [FAQ](faq.md) — Frequently asked questions

## What is Hermes TUI?

Hermes TUI runs entirely in your terminal. It defaults to using local models via
[Ollama](https://ollama.ai), so no data leaves your machine unless you configure a
remote provider.

### Key capabilities

- 💬 Streaming chat with any OpenAI-compatible LLM
- 🧠 Cross-session memory with full-text search
- 🛠️ Tool use (web search, file ops, terminal commands)
- 📦 Markdown-based skills system
- 🎨 Dark/light themes
- ⌨️ Keyboard-driven command palette

## Getting Started

```bash
# Install
pipx install hermes-tui

# Make sure Ollama is running with a model
ollama serve &
ollama pull qwen2.5:7b

# Launch
hermes-tui chat
```

## Project Links

- [GitHub Repository](https://github.com/hermes-tui/hermes-tui)
- [Issue Tracker](https://github.com/hermes-tui/hermes-tui/issues)
- [PyPI](https://pypi.org/project/hermes-tui/)
