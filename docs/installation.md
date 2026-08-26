# Installation Guide

## Requirements

- Python 3.11 or higher
- A terminal that supports 256 colors and Unicode
- (Optional) [Ollama](https://ollama.ai) for local models

## Install with pipx (recommended)

[pipx](https://pipx.pypa.io/) installs the application in an isolated environment
and makes the `hermes-tui` command available globally:

```bash
pipx install hermes-tui
```

To upgrade:

```bash
pipx upgrade hermes-tui
```

## Install with pip

```bash
pip install hermes-tui
```

We recommend using a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install hermes-tui
```

## Install from source

```bash
git clone https://github.com/hermes-tui/hermes-tui.git
cd hermes-tui
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Or using the Makefile:

```bash
make dev
```

## Run with Docker

Build the image:

```bash
docker build -t hermes-tui:latest .
```

Run interactively:

```bash
docker run -it --rm \
  -v $HOME/.hermes-tui:/root/.hermes-tui \
  hermes-tui:latest
```

Using Docker Compose:

```bash
docker-compose run --rm hermes-tui
```

## Set up Ollama (for local use)

Hermes TUI defaults to connecting to a local Ollama instance.

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Start the server:

   ```bash
   ollama serve
   ```

3. Pull a model:

   ```bash
   ollama pull qwen2.5:7b
   ```

4. Launch Hermes TUI:

   ```bash
   hermes-tui chat
   ```

## Verify installation

```bash
hermes-tui version
```

This should print the installed version.

## Troubleshooting

### `command not found: hermes-tui`

Make sure your Python `bin` directory is in your `PATH`. If using pipx, run
`pipx ensurepath`.

### Terminal rendering issues

Ensure your terminal supports 256 colors. Most modern terminals (iTerm2,
Windows Terminal, Alacritty, Kitty, GNOME Terminal) work well.

### Cannot connect to Ollama

Verify Ollama is running:

```bash
curl http://localhost:11434/v1/models
```

If Ollama is on a different host, update `base_url` in your config.
