# Configuration

Hermes TUI can be configured via a YAML file and environment variables.

## Config File Location

By default, the config file is at:

```
~/.hermes-tui/config.yaml
```

You can override this with the `--config` flag:

```bash
hermes-tui --config /path/to/config.yaml chat
```

Or set the `HERMES_TUI_CONFIG_DIR` environment variable:

```bash
export HERMES_TUI_CONFIG_DIR=/custom/path
```

On first launch, a default configuration is automatically created.

## Environment Variables

Any configuration option can be overridden with an environment variable using
the `HERMES_TUI_` prefix and `__` as the nested delimiter:

```bash
export HERMES_TUI_LLM__API_KEY=sk-your-key
export HERMES_TUI_LLM__MODEL=gpt-4o
export HERMES_TUI_LLM__BASE_URL=https://api.openai.com/v1
export HERMES_TUI_UI__THEME=light
export HERMES_TUI_MEMORY__ENABLED=false
```

Environment variables take priority over config file values.

## Full Configuration Reference

```yaml
llm:
  provider: openai_compatible    # Provider type
  base_url: http://localhost:11434/v1  # API endpoint
  api_key: ollama                # API key
  model: qwen2.5:7b             # Model name
  temperature: 0.7              # 0.0 - 2.0
  max_tokens: 4096              # Max response tokens
  timeout: 120.0                # Request timeout (seconds)
  max_retries: 3                # Retry attempts

ui:
  theme: dark                   # dark or light
  animation: true               # Enable animations
  word_wrap: true               # Wrap long lines
  show_token_count: true        # Show tokens in status bar

memory:
  enabled: true                 # Enable memory
  db_path: ~/.hermes-tui/memory.db  # SQLite path
  max_entries: 10000            # Max stored entries
  auto_prune: true              # Auto-prune old entries
  safety_scan: true             # Prompt injection detection

skills:
  skills_dir: ~/.hermes-tui/skills  # Skill directory
  auto_load: true               # Load skills on startup
  max_skills: 50                # Max loaded skills
```

## Provider Examples

### Ollama (local, default)

```yaml
llm:
  base_url: http://localhost:11434/v1
  api_key: ollama
  model: qwen2.5:7b
```

### OpenAI

```yaml
llm:
  base_url: https://api.openai.com/v1
  api_key: sk-your-api-key
  model: gpt-4o
```

### OpenRouter

```yaml
llm:
  base_url: https://openrouter.ai/api/v1
  api_key: sk-or-your-key
  model: anthropic/claude-3.5-sonnet
```

### DeepSeek

```yaml
llm:
  base_url: https://api.deepseek.com/v1
  api_key: sk-your-key
  model: deepseek-chat
```

### vLLM (self-hosted)

```yaml
llm:
  base_url: http://localhost:8000/v1
  api_key: dummy
  model: your-model-name
```

## CLI Commands

### Show current config

```bash
hermes-tui config show
hermes-tui config show --json
```

### Initialize config

```bash
hermes-tui config init
hermes-tui config init --force  # Overwrite existing
```

### Print config path

```bash
hermes-tui config path
```

## Configuration Priority

1. Environment variables (`HERMES_TUI_*`)
2. Config file values
3. Built-in defaults
