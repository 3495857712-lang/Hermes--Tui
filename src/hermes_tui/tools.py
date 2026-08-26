"""Tool registration and built-in tool implementations.

Provides a registry that produces OpenAI-compatible function-calling
schemas and executes tools with safe error handling.  The public API
supports both the decorator style (``@registry.register``) and the
explicit style (``registry.register(func, name=..., description=...)``).
"""

from __future__ import annotations

import inspect
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

logger = logging.getLogger(__name__)

_SENSITIVE_PARTS = {".ssh", ".gnupg", ".aws", ".config"}
_SENSITIVE_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
                    "shadow", "sudoers", "passwd", ".env", "credentials"}
MAX_FILE_SIZE = 100 * 1024  # 100 KB
_MAX_FILE_BYTES = MAX_FILE_SIZE

_PY_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

# PEP 563 deferred annotations arrive as strings; map them here.
_NAME_TO_JSON = {
    "str": "string", "string": "string",
    "int": "integer", "integer": "integer",
    "float": "number", "number": "number",
    "bool": "boolean", "boolean": "boolean",
    "list": "array", "array": "array",
    "dict": "object", "object": "object",
}


def _py_type_to_json(py_type: Any) -> str:
    """Map a Python annotation to a JSON Schema type name."""
    if py_type is inspect.Parameter.empty or py_type is None:
        return "string"
    # PEP 563: annotations can be strings.
    if isinstance(py_type, str):
        base = py_type.split("[", 1)[0].strip().lower()
        return _NAME_TO_JSON.get(base, "string")
    origin = getattr(py_type, "__origin__", None)
    if origin is not None:
        return _PY_TO_JSON.get(origin, "string")
    if isinstance(py_type, type):
        return _PY_TO_JSON.get(py_type, "string")
    return "string"


@dataclass
class ToolParameter:
    """Description of one tool parameter."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    enum: list[Any] | None = None


@dataclass
class ToolDefinition:
    """A registered tool with metadata and handler."""

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    handler: Callable[..., Any] | None = None

    def to_openai_schema(self) -> dict[str, Any]:
        """Return the OpenAI function-calling schema for this tool."""
        props: dict[str, Any] = {}
        required: list[str] = []
        for p in self.parameters:
            props[p.name] = {"type": p.type, "description": p.description}
            if p.enum:
                props[p.name]["enum"] = p.enum
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }

    def __getitem__(self, key: str) -> Any:
        """Allow dict-style access for backwards-compatibility (``meta["name"]``)."""
        if key in {"name", "description", "parameters", "handler"}:
            return getattr(self, key)
        schema = self.to_openai_schema()["function"]
        if key in schema:
            return schema[key]
        raise KeyError(key)


class ToolRegistry:
    """Registry of available tools."""

    def __init__(
        self,
        workspace: str | Path | None = None,
        enabled_names: list[str] | None = None,
    ) -> None:
        self.workspace = Path(workspace).expanduser().resolve() if workspace else None
        self._tools: dict[str, ToolDefinition] = {}
        self._enabled = set(enabled_names) if enabled_names else None

    # -- registration ---------------------------------------------------

    def register(
        self,
        func_or_name: Any = None,
        *,
        name: str | None = None,
        description: str | None = None,
        parameters: list[ToolParameter] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Register a tool.

        Can be used as a bare decorator (``@registry.register``),
        a called decorator (``@registry.register(name=...)``), or
        called directly (``registry.register(func, name=...)``).
        """
        # Called directly with a function as first positional arg.
        if callable(func_or_name) and name is None and description is None and parameters is None and not kwargs:
            return self._register_func(func_or_name)
        if callable(func_or_name):
            return self._register_func(
                func_or_name, name=name, description=description,
                parameters=parameters,
            )
        # Used as a decorator with/without kwargs: @register(...)
        def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or func_or_name or func.__name__
            self._register_func(
                func, name=tool_name, description=description,
                parameters=parameters, **kwargs,
            )
            return func
        return _decorator

    def _register_func(
        self,
        func: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
        parameters: list[ToolParameter] | None = None,
    ) -> Callable[..., Any]:
        tool_name = name or func.__name__
        tool_desc = description or (inspect.getdoc(func) or "").strip() or f"Tool {tool_name}"
        if parameters is None:
            parameters = self._infer_params(func)
        self._tools[tool_name] = ToolDefinition(
            name=tool_name, description=tool_desc,
            parameters=list(parameters), handler=func,
        )
        logger.debug("Registered tool: %s", tool_name)
        return func

    @staticmethod
    def _infer_params(func: Callable[..., Any]) -> list[ToolParameter]:
        sig = inspect.signature(func)
        params: list[ToolParameter] = []
        for pname, param in sig.parameters.items():
            if pname in {"self", "workspace"}:
                continue
            required = param.default is inspect.Parameter.empty
            ptype = _py_type_to_json(param.annotation)
            params.append(ToolParameter(
                name=pname, type=ptype, required=required,
            ))
        return params

    # -- query / execution ----------------------------------------------

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return OpenAI function schemas for enabled tools."""
        return [t.to_openai_schema() for t in self._tools.values()
                if self._is_enabled(t.name)]

    def list_names(self) -> list[str]:
        return [n for n in self._tools if self._is_enabled(n)]

    def get_definitions(self) -> list[dict[str, Any]]:
        return self.list_tools()

    def is_enabled(self, name: str) -> bool:
        return self._is_enabled(name)

    def _is_enabled(self, name: str) -> bool:
        if name not in self._tools:
            return False
        if self._enabled is None:
            return True
        return name in self._enabled

    async def execute(self, name: str, **kwargs: Any) -> str:
        """Execute a tool by name and return its string result."""
        tool = self._tools.get(name)
        if tool is None or tool.handler is None:
            return f"Error: unknown tool '{name}'"
        if not self._is_enabled(name):
            return f"Error: tool '{name}' is disabled"
        # If the handler expects a workspace and the registry has one, inject it.
        try:
            sig = inspect.signature(tool.handler)
            if "workspace" in sig.parameters and "workspace" not in kwargs:
                kwargs["workspace"] = self.workspace
        except (TypeError, ValueError):
            pass
        try:
            result = tool.handler(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            if result is None:
                return f"Tool '{name}' completed successfully."
            return str(result)
        except Exception as exc:
            logger.exception("Tool '%s' raised", name)
            return f"Error in '{name}': {exc}"


# ----------------------------------------------------------------------
# Path safety helpers
# ----------------------------------------------------------------------

def _is_sensitive(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & _SENSITIVE_PARTS:
        return True
    if path.name.lower() in _SENSITIVE_NAMES:
        return True
    return False


def _resolve_workspace(path: str, workspace: str | Path | None) -> Path:
    """Resolve *path* inside *workspace*, blocking traversal/sensitive targets."""
    # Reject explicit traversal segments up-front, matching test expectations.
    if path.startswith("../") or path.startswith("..\\"):
        raise ValueError(f"Path escapes workspace: {path}")
    ws = Path(workspace).expanduser().resolve() if workspace else Path.cwd()
    target = (ws / path).resolve()
    # Containment check.
    try:
        target.relative_to(ws)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace: {path}") from exc
    if _is_sensitive(target):
        raise ValueError(f"Refusing access to sensitive path: {target}")
    return target


# ----------------------------------------------------------------------
# Built-in tool implementations (public, importable)
# ----------------------------------------------------------------------

def get_time() -> str:
    """Return the current UTC date and time."""
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%d %H:%M:%S UTC")


def read_file(path: str, workspace: str | Path | None = None) -> str:
    """Read a text file (max 100 KB) from the workspace."""
    try:
        target = _resolve_workspace(path, workspace)
    except ValueError as exc:
        msg = str(exc).lower()
        if "sensitive" in msg:
            return f"Error: refusing access to sensitive path: {path}"
        raise
    if not target.exists():
        return f"Error: file not found: {target}"
    if not target.is_file():
        return f"Error: not a regular file: {target}"
    size = target.stat().st_size
    if size > MAX_FILE_SIZE:
        return f"Error: file too large ({size} bytes); max {MAX_FILE_SIZE}."
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Error reading file: {exc}"


def write_file(path: str, content: str, workspace: str | Path | None = None) -> str:
    """Write *content* to a file inside the workspace, creating parent dirs."""
    try:
        target = _resolve_workspace(path, workspace)
    except ValueError:
        raise
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {target}"
    except OSError as exc:
        return f"Error writing file: {exc}"


async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web with DuckDuckGo and return formatted results."""
    if not query.strip():
        return "Error: query must not be empty."
    num_results = max(1, min(num_results, 10))
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; HermesTUI/0.1)"},
            )
        if resp.status_code >= 400:
            return f"Web search failed: HTTP {resp.status_code}"
        html = resp.text
    except httpx.HTTPError as exc:
        return f"Web search failed: {exc}"

    pattern = r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
    blocks = re.findall(pattern, html, re.DOTALL)
    results: list[str] = []
    for url, title in blocks[:num_results]:
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        m = re.search(r"uddg=([^&]+)", url)
        if m:
            url = unquote(m.group(1))
        results.append(f"**{unescape(clean_title)}**\n{unescape(url)}")
    if not results:
        return f"No results found for '{query}'."
    return "\n\n".join(results)


# ----------------------------------------------------------------------
# Registry factories
# ----------------------------------------------------------------------

def create_default_registry(
    workspace: str | Path | None = None,
    enabled_tools: list[str] | None = None,
) -> ToolRegistry:
    """Create a :class:`ToolRegistry` pre-loaded with built-in tools."""
    registry = ToolRegistry(workspace=workspace, enabled_names=enabled_tools)
    registry.register(get_time)
    registry.register(read_file)
    registry.register(write_file)
    registry.register(
        web_search,
        name="web_search",
        description="Search the web and return titles + URLs.",
        parameters=[
            ToolParameter("query", "string", "Search query", required=True),
            ToolParameter("num_results", "integer", "Max results (1-10)",
                          required=False),
        ],
    )
    logger.info("Default tool registry created: %s", registry.list_names())
    return registry


def register_builtin_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register built-in tools onto an existing *registry* (test helper)."""
    ws = getattr(registry, "workspace", None)
    builtin = create_default_registry(workspace=ws)
    for name in builtin.list_names():
        tool = builtin.get_tool(name)
        if tool and tool.handler:
            registry.register(
                tool.handler,
                name=name,
                description=tool.description,
                parameters=tool.parameters,
            )
    return registry
