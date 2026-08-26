# Examples

This page provides practical examples of using Hermes TUI.

## Basic Chat

```bash
# Start chatting with the default model
hermes-tui chat
```

```
🧑 You: What is the capital of France?

🤖 Hermes: The capital of France is Paris. It's located in the
north-central part of the country along the Seine River.
```

## Switching Models

### In-app

```
/model llama3:8b
```

### CLI

```bash
hermes-tui chat --model gpt-4o --endpoint https://api.openai.com/v1
```

## Using Tools

Hermes automatically decides when to use tools:

```
🧑 You: Search the web for the latest Python release

🤖 Hermes: 🔧 Executing web_search...
🔧 web_search: Python 3.13.0 released on October 7, 2024. Key features
include...

The latest stable Python release is version 3.13.0, released on October 7,
2024. Major new features include a JIT compiler, improved error messages,
and removal of deprecated modules.
```

### File Operations

```
🧑 You: Read the README.md in my project

🤖 Hermes: 🔧 read_file("~/projects/my-app/README.md")
# My App
A fantastic application...

The README describes a project called "My App" with...
```

### Terminal Commands

Dangerous commands require confirmation:

```
🧑 You: Run git status in my project

🤖 Hermes: I'll run `git status` for you.
🔧 run_terminal("cd ~/projects/my-app && git status")
[Requires confirmation — press Y to proceed]
```

## Using Skills

Skills activate automatically based on your message:

```
🧑 You: Can you review this Python code?

[The code-review skill is matched and loaded automatically]

🤖 Hermes: I'll review your code using the code review skill.
Please share the code you'd like me to review...
```

## Managing Memory

```bash
# Search memories
hermes-tui memory --search "python"

# List recent
hermes-tui memory --list

# Count
hermes-tui memory --count
```

```
/memory
```

## Custom Configuration

```bash
# Use a specific config file
hermes-tui --config ./my-config.yaml chat

# Override with environment variables
HERMES_TUI_LLM__MODEL=mistral hermes-tui chat
```

## Docker

```bash
# Build
docker build -t hermes-tui .

# Run with persistent config
docker run -it --rm \
  -v $HOME/.hermes-tui:/root/.hermes-tui \
  hermes-tui
```

## Programmatic Usage

```python
import asyncio
from hermes_tui.agent import Agent
from hermes_tui.llm import OpenAICompatibleClient, ChatMessage
from hermes_tui.prompt import PromptBuilder
from hermes_tui.soul import Soul
from hermes_tui.tools import registry
from hermes_tui.skills import SkillLoader
from hermes_tui.memory import MemoryManager
from hermes_tui.database import Database

async def main():
    db = Database(":memory:")
    db.initialize()
    memory = MemoryManager(db)
    soul = Soul.default()
    skills = SkillLoader("/tmp/skills")
    skills.load()

    llm = OpenAICompatibleClient(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="qwen2.5:7b",
    )

    prompt_builder = PromptBuilder(soul, registry, skills, memory)
    agent = Agent(llm, prompt_builder, registry, memory)

    response = await agent.chat("Hello! What can you do?")
    print(response)

    await llm.aclose()
    db.close()

asyncio.run(main())
```
