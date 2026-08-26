---
name: example
description: An example skill demonstrating the skill format
version: 0.1.0
tags: [example, demo, help]
---

# Example Skill

This is an example skill that demonstrates how to structure a skill for
Hermes TUI with YAML frontmatter and Markdown content.

## When to Use

- When the user asks about examples or demos
- When the user asks how skills work
- When introducing the skill system

## Instructions

1. Explain that this is a demonstration skill.
2. Describe the three-level progressive loading:
   - Level 1: Metadata (name, version, tags) — always loaded
   - Level 2: Description — loaded when the skill is listed
   - Level 3: Full content — loaded when the skill matches
3. Mention that skills are plain Markdown files with YAML frontmatter.
4. Tell the user they can create their own skills in `~/.hermes-tui/skills/`.

## Frontmatter Format

```yaml
---
name: my-skill
description: Brief one-line description
version: 0.1.0
tags: [tag1, tag2]
---
```

The content after the closing `---` is the skill body, which can contain
any Markdown formatting.
