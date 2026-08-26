# Architecture

This document describes the internal architecture of Hermes TUI.

## Overview

Hermes TUI follows a layered architecture with clear separation between
the UI, agent orchestration, and infrastructure.

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ ChatView │  │ Sidebar  │  │ CommandPalette / etc │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
│       └──────────────┼───────────────────┘               │
│                      ▼                                    │
│              ┌──────────────┐                             │
│              │  HermesApp   │  (Textual App)              │
│              └──────┬───────┘                             │
├─────────────────────┼─────────────────────────────────────┤
│                     ▼                                     │
│               Agent Layer                                  │
│  ┌─────────────────────────────────────────────────┐     │
│  │                   AIAgent                        │     │
│  │  • Message loop    • Tool call execution         │     │
│  │  • Session mgmt    • Context compression         │     │
│  │  • Task delegation                               │     │
│  └──┬──────────┬──────────┬──────────┬──────────────┘     │
├─────┼──────────┼──────────┼──────────┼────────────────────┤
│     ▼          ▼          ▼          ▼                     │
│  Service Layer                                             │
│  ┌──────┐ ┌────────┐ ┌───────┐ ┌─────────┐               │
│  │ LLM  │ │ Memory │ │ Skills│ │  Tools  │               │
│  │Client│ │  (SQL) │ │ (MD)  │ │Registry │               │
│  └──┬───┘ └───┬────┘ └──┬────┘ └────┬────┘               │
├─────┼──────────┼─────────┼───────────┼────────────────────┤
│     ▼          ▼         ▼           ▼                     │
│  Infrastructure Layer                                      │
│  ┌──────┐ ┌────────┐ ┌───────┐ ┌─────────┐               │
│  │httpx │ │SQLite  │ │  FS   │ │subprocess│               │
│  │      │ │+ FTS5  │ │       │ │          │               │
│  └──────┘ └────────┘ └───────┘ └─────────┘               │
└───────────────────────────────────────────────────────────┘
```

## Core Modules

### `app.py` — HermesApp

The main Textual application. It:

- Composes the UI layout (ChatView, Sidebar, CommandPalette, StatusBar).
- Routes user messages to the agent.
- Streams responses back to the chat view.
- Handles slash commands and key bindings.
- Manages the application lifecycle.

### `agent.py` — AIAgent

The orchestration engine. It:

1. Receives user messages.
2. Builds the prompt via `PromptBuilder`.
3. Calls the LLM client.
4. Parses tool calls from the response.
5. Executes tools via the `ToolRegistry`.
6. Feeds results back to the LLM.
7. Repeats until a final response is produced (max 10 rounds).
8. Manages sessions (create, save, restore).

### `llm.py` — LLM Client

An async HTTP client for OpenAI-compatible APIs:

- Supports streaming via SSE.
- Implements retry with exponential backoff.
- Classifies errors (auth, rate limit, connection, server).
- Parses both streaming and non-streaming responses.
- Supports function/tool calling.

### `memory.py` — MemoryManager

Persistent memory with SQLite:

- Three layers: working, episodic, procedural.
- FTS5 full-text search.
- Automatic fact extraction (rule-based).
- Prompt injection safety scanning.
- Access counting and LRU pruning.

### `skills.py` — SkillLoader

Markdown-based skill system:

- Scans directories for `skill.md` files.
- Parses YAML frontmatter.
- Three-level progressive loading.
- Keyword/tag-based skill matching.

### `tools.py` — ToolRegistry

Function-calling infrastructure:

- `@tool` decorator for easy registration.
- Automatic JSON schema generation from signatures/docstrings.
- Built-in tools (web search, file I/O, terminal, time).
- Sync and async tool execution.
- User confirmation for dangerous tools.

### `prompt.py` — PromptBuilder

Assembles the system prompt from:

1. SOUL.md personality.
2. Environment info.
3. Relevant skill content (matched to user message).
4. Relevant memories (FTS search).
5. Tool descriptions.
6. Message history with context compression.

### `config.py` — Config

Pydantic-based configuration:

- YAML file loading/saving.
- Environment variable overrides.
- Auto-generation of default config.
- Validation of all fields.

### `database.py` — Database

SQLite connection management:

- Thread-local connections.
- Schema migrations with version tracking.
- FTS5 virtual tables and sync triggers.
- Context managers for transactions.

## Data Flow

### Sending a Message

```
User types message
       │
       ▼
ChatView.on_input_submitted
       │ posts MessageSent
       ▼
HermesApp.on_message_sent
       │
       ▼
AIAgent.chat(message)
       │
       ├──▶ PromptBuilder.build_messages()
       │        ├── SOUL personality
       │        ├── Matched skills
       │        ├── Relevant memories
       │        └── Tool descriptions
       │
       ├──▶ LLMClient.chat(messages, tools, stream=True)
       │
       ▼
Stream chunks ──▶ ChatView (real-time display)
       │
       ├── If tool_calls:
       │     ├──▶ ToolRegistry.execute()
       │     ├── Add tool result to messages
       │     └── Loop back to LLM
       │
       └── Final response
              ├──▶ Display in ChatView
              ├──▶ MemoryManager.maybe_store_facts()
              └──▶ Update Sidebar/StatusBar
```

### Configuration Loading

```
HermesApp.__init__
       │
       ▼
get_config()
       │
       ├── Check ~/.hermes-tui/config.yaml
       │     └── If missing, create from bundled template
       │
       ├── Load YAML values
       │
       └── Override with HERMES_TUI_* env vars
              │
              ▼
         Validated Config
```

## Async Model

All I/O operations are async:

- LLM API calls use `httpx.AsyncClient`.
- Tool execution uses `asyncio.to_thread` for sync functions.
- Streaming uses async iterators.
- The Textual event loop manages the UI without blocking.

## Testing

The test suite uses:

- `pytest` with `pytest-asyncio` for async tests.
- `unittest.mock` for LLM client mocking.
- Temporary directories and in-memory SQLite for isolation.
- Factory fixtures in `conftest.py`.

## Design Decisions

1. **Default to Ollama**: Privacy-first, works offline, no API key needed.
2. **SQLite + FTS5**: No external database dependency, full-text search built in.
3. **Markdown skills**: Human-readable, easy to author, no code required.
4. **Pydantic config**: Type-safe, validated, with env var support.
5. **Progressive skill loading**: Keeps context window efficient.
6. **No heavy LLM for fact extraction**: Rule-based to avoid extra API calls.
