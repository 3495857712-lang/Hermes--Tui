# Tool Development Guide

Tools are Python functions that the AI agent can call to perform actions
(fetching web results, reading files, running commands, etc.). This guide
explains how to create and register custom tools.

## Built-in Tools

| Tool | Description | Confirmation |
|------|-------------|-------------|
| `get_time` | Get current date and time | No |
| `web_search` | Search the web via DuckDuckGo | No |
| `read_file` | Read a text file | No |
| `write_file` | Write content to a file | Yes |
| `run_terminal` | Execute a shell command | Yes |
| `list_directory` | List directory contents | No |

## Creating a Tool

Use the `@tool` decorator to register a function:

```python
from hermes_tui.tools import tool

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression.

    Args:
        expression: The math expression to evaluate, e.g. "2 + 2".
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"
```

That's it! The docstring and type annotations are automatically converted
into a JSON schema that the LLM uses to understand how to call the tool.

## Async Tools

Tools can be async:

```python
import httpx
from hermes_tui.tools import tool

@tool
async def fetch_url(url: str) -> str:
    """Fetch the content of a URL.

    Args:
        url: The URL to fetch.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        return resp.text[:5000]
```

## Requiring Confirmation

For potentially dangerous operations, set `requires_confirmation=True`:

```python
from hermes_tui.tools import tool

@tool(requires_confirmation=True)
def delete_file(path: str) -> str:
    """Delete a file.

    Args:
        path: Path to the file to delete.
    """
    import os
    os.remove(path)
    return f"Deleted {path}"
```

When the LLM calls this tool, the user will be prompted to confirm before
execution.

## Using the ToolRegistry

For more control, use the `ToolRegistry` directly:

```python
from hermes_tui.tools import ToolRegistry

registry = ToolRegistry()

@registry.register(name="my_tool", description="Does something")
def my_function(query: str, limit: int = 10) -> str:
    """..."""
    return f"Results for {query} (limit={limit})"
```

## Tool Schema Generation

The schema is generated automatically from:

- **Function name**: becomes the tool name
- **Docstring summary**: first line becomes the description
- **`Args:` section**: parameter descriptions
- **Type annotations**: JSON schema types

### Supported Types

| Python Type | JSON Schema Type |
|-------------|-----------------|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list` | `array` |
| `dict` | `object` |

### Google-style Docstring

```python
def my_tool(name: str, count: int) -> str:
    """Short description of the tool.

    Longer explanation can go here.

    Args:
        name: The name parameter.
        count: How many items.
    """
```

## Registering Tools at Startup

To add custom tools, create a Python module and register them:

```python
# my_tools.py
from hermes_tui.tools import tool

@tool
def my_custom_tool(query: str) -> str:
    """Search my custom database.

    Args:
        query: Search query.
    """
    # Your implementation
    return "results"
```

Then import the module before launching the app. The `@tool` decorator
registers on the global registry automatically.

## Tool Execution

When the LLM requests a tool call:

1. The agent receives the tool name and arguments from the LLM response.
2. The `ToolRegistry` looks up the tool.
3. If `requires_confirmation=True`, the user is prompted.
4. The tool function is executed (async tools are awaited, sync tools run
   in a thread).
5. The result is converted to a string and added to the message history.
6. The LLM receives the result and can continue or respond.

## Best Practices

- Write clear, concise docstrings — the LLM reads them!
- Validate all inputs.
- Return results as strings (they go directly into the conversation).
- Handle errors gracefully and return error messages rather than raising.
- Use `requires_confirmation` for any destructive operation.
- Keep tool execution fast; long operations should use async.
- Limit output size to avoid consuming too many tokens.
