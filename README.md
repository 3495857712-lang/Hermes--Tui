<p align="center">
  <img src="assets/logo.png" alt="Hermes TUI" width="160" height="160" />
</p>

<h1 align="center">Hermes TUI</h1>

<p align="center">
  <strong>A self-evolving terminal AI agent — not another chat bubble in a box.</strong>
</p>

<p align="center">
  Visible reasoning · Versioned memory · Human-reviewed skill evolution · Local-first
</p>

<p align="center">
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License" /></a>
  <a href="#"><img src="https://img.shields.io/badge/code%20style-ruff-000000.svg" alt="Ruff" /></a>
  <a href="#"><img src="https://img.shields.io/badge/mypy-strict-blue.svg" alt="mypy" /></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg" alt="Platform" /></a>
</p>

---

## Why Hermes?

Most terminal AI tools wrap a chatbot in a TUI. Hermes treats the agent as a **cognitive system you can inspect, reverse, and improve**:

| Innovation | What you get |
|---|---|
| **Thought Graph** | Every LLM call, tool run, and memory recall is a node you can navigate — not a flat log |
| **Memory Git** | Memory mutations as commits: branch, diff, rollback |
| **Skill Forge** | Post-task reflection proposes skill PRs you accept or reject |
| **Context Map** | Live token budget: see what is in context, pin what must stay |
| **Pipe Commands** | Unix-style composition: `/recall x \| /grep y \| /summarize 3` |

Inspired by [Hermes Agent](https://github.com/NousResearch/hermes-agent)'s self-evolution loop — with one hard rule: **nothing mutates silently**. Every change is visible, reversible, and human-reviewed.

---

## Demo layout

```
┌──────────────┬──────────────────────┬──────────────┐
│ Thought      │  Conversation &      │ Context Map  │
│ Graph        │  Pipe Commands       │ Token heat-  │
│ Branchable   │  /recall \| /grep    │ map · pin /  │
│ reasoning    │  \| /summarize       │ evict        │
├──────────────┴──────────────────────┴──────────────┤
│ Memory Git  ·  Skill Forge proposals               │
└────────────────────────────────────────────────────┘
```

---

## Quick start

```bash
# Recommended
pipx install hermes-tui

# Or
pip install hermes-tui

# Launch (first run writes ~/.hermes-tui/config.yaml)
hermes-tui

# Local / offline with Ollama
hermes-tui --model qwen2.5:7b
```

### From source

```bash
git clone https://github.com/3495857712-lang/hermes-tui.git
cd hermes-tui
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
hermes-tui
```

Default LLM endpoint: OpenAI-compatible **Ollama** at `http://localhost:11434/v1`.

---

## What makes it different

**Not a thin OpenAI wrapper.** Hermes is built around five product bets:

1. **Cognition is a graph** — branches when the agent explores alternatives; filter by node type with `f`, navigate with `j/k`.
2. **Memory has history** — `/memory log`, `/memory diff`, `/memory rollback` instead of an opaque vector dump.
3. **Self-improvement is a PR** — Skill Forge turns reflection into auditable proposals, not silent prompt rewrites.
4. **Context is a budget you own** — pin critical facts; see why something was compressed or evicted.
5. **Unix DNA** — slash commands compose with `|` for introspection pipelines.

**Local-first by default:** SQLite + FTS5, no telemetry, API keys via env — nothing leaves your machine unless you point it at a cloud provider.

---

## Key bindings

| Key | Action |
|-----|--------|
| `Ctrl+G` | Focus Thought Graph |
| `Ctrl+C` | Focus chat input |
| `Ctrl+M` | Focus Context Map |
| `Ctrl+F` | Toggle Memory Git / Skill Forge |
| `Ctrl+R` | Reflect on last exchange |
| `Ctrl+P` | Command palette |
| `Ctrl+D` | Toggle dark / light |
| `Ctrl+Q` | Quit |

## Slash commands

| Command | Description |
|---------|-------------|
| `/help` | Show commands |
| `/recall <query>` | Search long-term memory |
| `/summarize [N]` | Summarize to N points |
| `/grep <pattern>` | Filter lines |
| `/context show\|pin\|unpin\|clear` | Manage context window |
| `/compact` | Compress history |
| `/history [last N]` | Recent messages |
| `/reflect` | Post-task reflection |
| `/forge propose\|list\|accept\|reject` | Skill proposals |
| `/skill list\|show\|create` | Manage skills |
| `/model <name>` | Switch model |

```bash
/history last 10 | /grep error | /summarize 5
```

---

## Architecture (short)

```
hermes_tui/
├── bootstrap.py         # Wires Config → services → EnhancedAIAgent → TUI
├── enhanced_agent.py    # Thought Graph · Memory Git · Forge · Context Map
├── thought_graph.py     # Non-linear reasoning graph
├── memory_git.py        # Version-controlled memory
├── skill_forge.py       # Self-evolution proposals
├── context_map.py       # Token budget visualization
├── pipe_commands.py     # Composable slash commands
├── llm.py / memory.py / skills.py / tools.py
└── ui/app.py            # Three-panel Textual workspace
```

See [docs/architecture.md](docs/architecture.md) for the full layer diagram.

---

## Configuration

`~/.hermes-tui/config.yaml` (override with `HERMES_TUI_*` env vars):

```yaml
llm:
  provider: openai_compatible
  base_url: http://localhost:11434/v1
  api_key: ollama
  model: qwen2.5:7b
  temperature: 0.7
  stream: true

memory:
  enabled: true

skills:
  skills_dir: ~/.hermes-tui/skills
  auto_load: true

agent:
  max_tool_iterations: 5
  context_window_tokens: 8000
```

---

## Development

```bash
make dev          # deps + pre-commit
make test         # pytest
make lint         # ruff
make typecheck    # mypy
make check        # all of the above
```

---

## Roadmap

- [x] Bootstrap factory + CLI launch path
- [x] Three-panel Thought Graph / Chat / Context Map UI
- [ ] Unify agent loop (single orchestration path)
- [ ] Persist Memory Git commits to SQLite
- [ ] Skill Forge accept → write `SKILL.md` on disk
- [ ] Richer streaming + tool-call UX

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and design critiques welcome — especially around visibility and reversibility of agent behavior.

## License

[MIT](LICENSE)

---

<p align="center">
  <sub>
    Built for people who want agents they can <em>trust because they can see them</em>.
  </sub>
</p>
