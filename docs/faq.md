# Frequently Asked Questions

## General

### What is Hermes TUI?

Hermes TUI is a terminal-based AI chat client and agent framework. It provides
a beautiful Textual-based interface for interacting with LLMs, with built-in
support for memory, skills, and tool use.

### Is Hermes TUI related to Nous Research's Hermes?

Hermes TUI is inspired by the concept of Nous Research's Hermes Agent but is
an independent open-source project. It is not affiliated with or endorsed by
Nous Research.

### Does it cost money?

No, Hermes TUI is free and open source under the MIT license. However, using
commercial LLM APIs (like OpenAI) may incur costs from the API provider. Using
local models via Ollama is completely free.

### Does it work offline?

Yes! When configured with a local Ollama instance, Hermes TUI runs entirely
offline. The default configuration points to `http://localhost:11434/v1`.

## Setup

### Which terminals are supported?

Any modern terminal with 256-color and Unicode support should work, including:

- iTerm2 (macOS)
- Windows Terminal
- Alacritty
- Kitty
- GNOME Terminal
- Konsole
- WezTerm

### Can I use it on Windows?

Yes. Use Windows Terminal for the best experience. Python 3.11+ is required.

### How do I use a different model?

```bash
hermes-tui chat --model gpt-4o
```

Or edit `~/.hermes-tui/config.yaml` and change the `model` field.

In the TUI: `/model <model-name>`

### How do I use OpenAI instead of Ollama?

Set the `base_url` and `api_key`:

```yaml
llm:
  base_url: https://api.openai.com/v1
  api_key: sk-your-key
  model: gpt-4o
```

## Features

### Does Hermes TUI store my data?

Memory entries are stored locally in `~/.hermes-tui/memory.db` (SQLite). No
data is sent anywhere except to the configured LLM endpoint. You can disable
memory in the config.

### Can I disable memory?

Yes, set `memory.enabled: false` in your config, or use the Settings screen
(Ctrl+S).

### How do I create a custom skill?

See the [Skills documentation](skills.md). Skills are simple Markdown files
with YAML frontmatter placed in `~/.hermes-tui/skills/`.

### Can I add custom tools?

Yes! Use the `@tool` decorator. See the [Tools documentation](tools.md) and
the `examples/custom_tool.py` file.

## Troubleshooting

### "Cannot connect to LLM API"

1. Ensure Ollama is running: `ollama serve`
2. Verify the endpoint: `curl http://localhost:11434/v1/models`
3. Check your `base_url` in the config.
4. If using a remote API, verify your API key.

### Text rendering looks wrong

Ensure your terminal supports Unicode and 256 colors. Try a different terminal
emulator. Set your `TERM` environment variable appropriately (e.g.,
`xterm-256color`).

### The TUI crashes on startup

Try running with verbose logging:

```bash
hermes-tui -v chat
```

Check that Python 3.11+ is installed: `python --version`

### How do I reset my configuration?

```bash
hermes-tui config init --force
```

Or delete the config file and restart:

```bash
rm ~/.hermes-tui/config.yaml
```

### How do I report a bug?

Please open an issue on [GitHub](https://github.com/hermes-tui/hermes-tui/issues)
with the output of `hermes-tui version`, your OS, and steps to reproduce.

## Development

### How do I set up a development environment?

```bash
git clone https://github.com/hermes-tui/hermes-tui.git
cd hermes-tui
make dev
```

### How do I run tests?

```bash
make test
```

### How do I run linters?

```bash
make lint
```
