# Memory System

Hermes TUI includes a persistent memory system that allows the AI to remember
information across conversations using SQLite with FTS5 full-text search.

## Memory Layers

The system implements a three-layer memory model:

### Working Memory

- **Scope**: Current session only.
- **Purpose**: Short-term context for the ongoing conversation.
- **Persistence**: Cleared when starting a new session.
- **Use case**: Intermediate facts, current task state.

### Episodic Memory

- **Scope**: Cross-session persistence.
- **Purpose**: Facts and observations about the user and past interactions.
- **Persistence**: Stored in SQLite until pruned.
- **Use case**: User preferences, past decisions, project context.

### Procedural Memory

- **Scope**: Cross-session persistence.
- **Purpose**: How-to knowledge linked to skills.
- **Persistence**: Stored in SQLite.
- **Use case**: Learned workflows, skill-specific knowledge.

## How Memory Is Used

1. When you send a message, the system searches episodic and procedural
   memories for relevant entries using FTS5 full-text search.
2. Relevant memories are injected into the system prompt.
3. After the assistant responds, simple rule-based extraction identifies
   potential facts worth remembering (e.g., "I prefer...", "My name is...").
4. Extracted facts are stored automatically.

## Safety

All memory entries pass through a prompt injection scanner that detects
common attack patterns like:

- "Ignore all previous instructions"
- "You are now a different assistant"
- Special token injection (`<|im_start|>`, `[INST]`, etc.)

Entries that fail the scan are rejected.

## CLI Commands

### View recent memories

```bash
hermes-tui memory --list
```

### Search memories

```bash
hermes-tui memory --search "python"
```

### Count entries

```bash
hermes-tui memory --count
```

### Clear all memories

```bash
hermes-tui memory --clear
```

### In-app commands

```
/memory          # Show recent memories in the chat
```

## Configuration

```yaml
memory:
  enabled: true
  db_path: ~/.hermes-tui/memory.db
  max_entries: 10000
  auto_prune: true
  safety_scan: true
```

## Database Schema

```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    tags TEXT DEFAULT '',
    layer TEXT NOT NULL DEFAULT 'episodic',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0
);
```

An FTS5 virtual table (`memories_fts`) provides full-text indexing on the
`key`, `content`, and `tags` columns, kept in sync via triggers.

## Pruning

When the entry count exceeds `max_entries`, the system automatically removes
the least recently accessed entries, prioritizing:

1. Working-layer entries first
2. Then episodic entries
3. Procedural entries are preserved longest

## Privacy

- Memory is stored locally in SQLite.
- No memory data is sent to external services.
- You can disable memory entirely with `memory.enabled: false`.
- You can inspect the database with any SQLite client:

```bash
sqlite3 ~/.hermes-tui/memory.db "SELECT key, content FROM memories LIMIT 10;"
```
