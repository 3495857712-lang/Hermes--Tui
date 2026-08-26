# Skills System

Skills are Markdown files that provide the AI with specialized instructions for
specific tasks. They are progressively loaded to keep the context window efficient.

## How It Works

Skills use a three-level progressive loading system:

1. **Metadata** (always loaded): Name, version, and tags from the YAML frontmatter.
2. **Description** (loaded when listing): The one-line description shown in the
   skills list and included in the system prompt.
3. **Full content** (loaded on match): The complete Markdown body is injected
   into the prompt only when the user's message matches the skill's tags or
   keywords.

This ensures that only relevant skill instructions consume context tokens.

## Skill File Format

A skill is a directory containing a `skill.md` file:

```
~/.hermes-tui/skills/
├── code-review/
│   └── skill.md
├── debugging/
│   └── skill.md
└── writing/
    └── skill.md
```

The `skill.md` file uses YAML frontmatter followed by Markdown content:

```markdown
---
name: code-review
description: Review code for bugs, style issues, and improvements
version: 1.0.0
tags: [code, review, python, javascript, quality]
---

# Code Review Assistant

You are an expert code reviewer. When the user asks for a review:

1. First, understand the purpose of the code.
2. Check for bugs, security issues, and edge cases.
3. Evaluate code style and readability.
4. Suggest specific improvements with code examples.
5. Be constructive — explain why something is an issue.

## Focus Areas

- Correctness and edge cases
- Security vulnerabilities
- Performance
- Naming and readability
- Test coverage
```

## Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique skill identifier (lowercase, hyphens) |
| `description` | Yes | One-line description (shown in skills list) |
| `version` | No | Semantic version string (default: `0.1.0`) |
| `tags` | No | List or comma-separated string of tags |

## Skill Matching

When the user sends a message, the system:

1. Tokenizes the message into words.
2. Scores each loaded skill based on:
   - Tag matches (highest weight)
   - Name matches
   - Description keyword overlap
3. Injects the full content of the top-matching skills into the prompt.
4. Lists remaining skills by name only.

## Managing Skills

### List loaded skills

```bash
hermes-tui skills --list
```

### Create an example skill

```bash
hermes-tui skills --create-example
```

### In-app commands

```
/skills          # List loaded skills
```

## Bundled Skills

Hermes TUI comes with a code review assistant skill in the `skills/` directory.
On startup, skills are loaded from:

1. The bundled `skills/` directory (installed with the package)
2. The user's `~/.hermes-tui/skills/` directory

## Best Practices

- Keep skills focused on one task or domain.
- Use specific tags that users are likely to type.
- Write clear, actionable instructions.
- Include examples when helpful.
- Use Markdown formatting for structure.
- Don't duplicate information already in the SOUL.md personality.

## Example: Creating a Skill

```bash
mkdir -p ~/.hermes-tui/skills/git-helper
```

Create `~/.hermes-tui/skills/git-helper/skill.md`:

```markdown
---
name: git-helper
description: Help with Git commands, workflows, and resolving conflicts
version: 1.0.0
tags: [git, version-control, commit, merge, rebase, conflict]
---

# Git Helper

Assist the user with Git operations.

## Guidelines

- Prefer clear, descriptive commit messages.
- Explain what each command does before suggesting it.
- For destructive operations (reset --hard, push --force), warn the user.
- When resolving conflicts, explain both sides of the conflict.
```

Restart Hermes TUI or the skill will be loaded on next launch.
