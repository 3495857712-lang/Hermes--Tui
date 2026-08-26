# Contributing to Hermes TUI

Thank you for your interest in contributing to Hermes TUI! This document provides
guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Environment Setup](#development-environment-setup)
- [Code Standards](#code-standards)
- [Pull Request Process](#pull-request-process)
- [Commit Message Convention](#commit-message-convention)
- [Issue Reporting Guide](#issue-reporting-guidelines)
- [Contributing Skills](#contributing-skills)
- [Contributing Tools](#contributing-tools)
- [Documentation Contributions](#documentation-contributions)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code. Please report unacceptable
behavior to conduct@hermes-tui.dev.

## Development Environment Setup

### Prerequisites

- Python 3.11 or higher
- Git
- Make (optional, for convenience targets)

### Step 1: Fork and Clone

1. Fork the repository on GitHub: https://github.com/hermes-tui/hermes-tui/fork
2. Clone your fork locally:

```bash
git clone https://github.com/YOUR_USERNAME/hermes-tui.git
cd hermes-tui
```

3. Add the upstream remote:

```bash
git remote add upstream https://github.com/hermes-tui/hermes-tui.git
```

### Step 2: Set Up the Development Environment

Using Make (recommended):

```bash
make dev
```

This will:
- Install the package in editable mode with all development dependencies
- Install pre-commit hooks

Without Make:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

### Step 3: Verify the Setup

```bash
make check
```

This runs linting, type checking, and tests. If everything passes, you're ready
to start contributing!

## Code Standards

### Linting and Formatting

We use [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting:

```bash
# Check for lint errors
make lint

# Auto-format code
make format
```

Ruff configuration is in `pyproject.toml`. The line length is 100 characters.

### Type Checking

We use [Mypy](https://mypy.readthedocs.io/) with strict settings:

```bash
make typecheck
```

All functions must have complete type annotations. The `src/` directory must pass
`mypy --strict`. Tests are checked with a slightly relaxed configuration.

### Testing

We use [pytest](https://docs.pytest.org/) with `pytest-asyncio` for async tests:

```bash
# Run all tests
make test

# Run with coverage
make test-cov
```

- All new features must include tests
- Bug fixes must include a regression test
- Test files go in the `tests/` directory, mirroring the `src/` structure
- Use `pytest-asyncio` for async test functions
- Use `respx` for mocking HTTP requests
- Aim for at least 80% code coverage on new code

### General Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) as enforced by Ruff
- Write descriptive docstrings in Google style
- Keep functions focused and under 50 lines where possible
- Prefer composition over inheritance
- Use type hints everywhere
- Handle errors explicitly — no bare `except:` clauses

## Pull Request Process

### Branch Naming Convention

Create a feature branch from `develop`:

| Prefix   | Purpose                          | Example                    |
|----------|----------------------------------|----------------------------|
| `feat/`  | New features                     | `feat/web-search-tool`     |
| `fix/`   | Bug fixes                        | `fix/memory-fts-crash`     |
| `docs/`  | Documentation changes            | `docs/skill-guide`         |
| `refactor/` | Code refactoring without behavior change | `refactor/agent-loop` |
| `test/`  | Adding or improving tests        | `test/tool-registry`       |
| `chore/` | Build, CI, dependency changes    | `chore/upgrade-textual`    |

### Before Submitting

1. Ensure your branch is up to date with `develop`:
   ```bash
   git fetch upstream
   git rebase upstream/develop
   ```

2. Run all checks:
   ```bash
   make check
   ```

3. Update documentation if your change affects user-facing behavior.

4. Add an entry to `CHANGELOG.md` under the `[Unreleased]` section.

### Submitting the PR

1. Push your branch to your fork.
2. Open a Pull Request against the `develop` branch.
3. Fill out the PR template completely.
4. Link any related issues using keywords (e.g., "Closes #123").
5. Request review from a maintainer.

### PR Review Process

- A maintainer will review your PR within 3 business days.
- Address review feedback by pushing new commits (don't force-push during review).
- Once approved, a maintainer will merge your PR.
- We use squash merges to keep history clean.

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<optional scope>): <description>

<optional body>

<optional footer(s)>
```

### Types

| Type         | Description                                                  |
|--------------|--------------------------------------------------------------|
| `feat`       | A new feature                                                |
| `fix`        | A bug fix                                                    |
| `docs`       | Documentation only changes                                   |
| `style`      | Changes that do not affect code meaning (formatting, etc.)   |
| `refactor`   | A code change that neither fixes a bug nor adds a feature    |
| `test`       | Adding missing tests or correcting existing tests            |
| `chore`      | Changes to build process, tooling, or dependencies           |
| `perf`       | A code change that improves performance                      |
| `ci`         | Changes to CI configuration                                  |

### Examples

```
feat(tools): add web search tool with DuckDuckGo integration
fix(memory): handle empty FTS5 query without crashing
docs(skills): clarify progressive loading behavior
refactor(agent): extract tool execution into separate class
test(config): add test for multi-profile switching
chore(deps): upgrade textual to 0.85.0
```

### Rules

- Use the imperative mood ("add" not "added")
- Do not capitalize the first letter of the description
- No period at the end of the description
- Keep the subject line under 72 characters
- Reference issues in the footer when applicable

## Issue Reporting Guide

### Bug Reports

1. Check that the bug hasn't already been reported.
2. Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml).
3. Include as much detail as possible:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Environment (OS, Python version, Hermes TUI version)
   - LLM provider being used
4. Include logs if available (`~/.hermes-tui/logs/`).
5. If possible, attach a screenshot or recording.

### Feature Requests

1. Check that the feature hasn't already been requested.
2. Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml).
3. Clearly describe the problem you're trying to solve.
4. Suggest a solution if you have one.
5. Describe alternatives you've considered.

### Security Issues

Please do **not** open public issues for security vulnerabilities. See
[SECURITY.md](SECURITY.md) for reporting instructions.

## Contributing Skills

Skills are markdown files with YAML frontmatter that teach Hermes TUI new
capabilities. To contribute a skill:

1. Create a new directory under `skills/` with a descriptive name.
2. Add a `skill.md` file with the required frontmatter:
   ```yaml
   ---
   name: your-skill-name
   description: Brief description of when this skill should activate
   version: 1.0.0
   tags: [relevant, tags]
   ---
   ```
3. Write the skill content using clear, step-by-step instructions.
4. Add any reference files to a `references/` subdirectory.
5. Test your skill by placing it in `~/.hermes-tui/skills/` and verifying
   Hermes TUI activates it for relevant queries.
6. Submit a PR with the label `skill`.

See [docs/skills.md](docs/skills.md) for the full skill authoring guide.

## Contributing Tools

Tools are Python functions decorated with `@registry.register`. To contribute
a tool:

1. Create a new file in `src/hermes_tui/tools/`.
2. Use the `@registry.register` decorator with type hints.
3. Include comprehensive error handling.
4. Add tests in `tests/tools/`.
5. Update `docs/tools.md` with documentation.
6. Submit a PR with the label `tool`.

See [docs/tools.md](docs/tools.md) for the full tool development guide.

## Documentation Contributions

Documentation is in the `docs/` directory and is written in Markdown.

- Use clear, concise language
- Include code examples where helpful
- Verify all commands and examples work
- Update documentation when changing user-facing behavior
- The `docs/index.md` file is the entry point

Thank you for contributing to Hermes TUI! 🎉
