# Security Policy

## Supported Versions

Security updates are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. We appreciate your efforts to
responsibly disclose your findings.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to:

**security@hermes-tui.dev**

You should receive a response within 48 hours. If for some reason you do not,
please follow up via email to ensure we received your original message.

### What to Include

Please include as much of the following information as possible:

- Type of vulnerability (e.g., buffer overflow, SQL injection, cross-site scripting)
- Full paths of source file(s) related to the manifestation
- Location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability, including how an attacker might exploit it

### Response Process

1. **Acknowledgment**: We will acknowledge receipt of your report within 48 hours.
2. **Investigation**: We will investigate the issue and may contact you for
   additional information.
3. **Initial Assessment**: Within 5 business days, we will provide an initial
   assessment of the vulnerability and our planned response.
4. **Fix Development**: We will develop and test a fix.
5. **Disclosure**: After the fix is released, we will publicly disclose the
   vulnerability (crediting the reporter if desired).

We aim to resolve critical vulnerabilities within 7 business days.

## Security Measures

### Local Data Storage

- All chat history, memory, and configuration data is stored **locally** on
  your machine in `~/.hermes-tui/`.
- The database uses SQLite and is protected by file system permissions
  (set to `0600` on Unix systems).
- No chat data is sent to any third party except the configured LLM provider
  needed to generate responses.
- You can inspect the database at any time using standard SQLite tools.

### API Key Handling

- API keys are never stored in plaintext configuration files.
- Keys are read from environment variables or a `.env` file with restricted
  file permissions.
- API keys are not logged or included in error reports.
- When using Docker, keys are passed via environment variables and never
  baked into images.
- The `/reset` command can clear all stored data if you need to revoke access.

### Tool Permission Control

- Tools that execute system commands (bash, file write) require explicit
  user confirmation before execution.
- File system access is restricted to paths you explicitly grant.
- Tool permissions are configurable in `config.yaml`:
  ```yaml
  tools:
    bash:
      enabled: true
      confirm: true
      allowed_paths:
        - ~/projects
    file_write:
      enabled: true
      confirm: true
  ```
- Network access is only available through the built-in web search tool
  or custom tools you explicitly enable.

### Input Sanitization

- All user inputs are validated and sanitized before being passed to tools.
- File paths are resolved and checked against allowed path lists.
- Shell commands are not interpolated with user input.
- Markdown output is sanitized to prevent terminal injection (no raw escape
  sequences from LLM output).

## Known Security Considerations

### Prompt Injection

Hermes TUI is an AI agent that processes natural language instructions. As
with all LLM-based systems, it may be vulnerable to prompt injection attacks
where untrusted content (e.g., web pages, files) contains instructions that
could alter the agent's behavior.

Mitigations:
- Tool execution always requires user confirmation.
- The agent distinguishes between user instructions and tool output content.
- System prompts are protected from user modification.

**Recommendation**: Do not use Hermes TUI with untrusted content in
environments where unauthorized tool execution could cause harm. Always review
tool calls before confirming.

### Terminal Tool Risks

The bash execution tool runs commands on your system. While we require
confirmation before execution, there is inherent risk in running AI-generated
commands.

Mitigations:
- All commands are shown to you before execution.
- You can deny any command.
- Commands run with your user permissions, not root.
- Path restrictions limit file access scope.

**Recommendation**: Review every command carefully before approving. Never
run Hermes TUI as root or with elevated privileges.

### Dependency Supply Chain

We use Dependabot to monitor dependencies for known vulnerabilities. All
dependencies are pinned in `requirements.txt` for reproducible builds.

### Docker Security

- The Docker image runs as a non-root user (`hermes`).
- The container has no host network access by default.
- Only the `~/.hermes-tui` directory is mounted.
- The image is scanned for vulnerabilities during CI.

## Disclosure Policy

We follow a coordinated disclosure model:

1. The reporter reports the vulnerability privately.
2. We develop and test a fix.
3. We release a patched version.
4. We publicly disclose the vulnerability after users have had reasonable
   time to update.

We are happy to credit reporters who wish to be named. If you prefer to remain
anonymous, we will respect that.

## Contact

- Security email: security@hermes-tui.dev
- General inquiries: hello@hermes-tui.dev
- GitHub: https://github.com/hermes-tui/hermes-tui
