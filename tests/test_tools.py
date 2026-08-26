"""Tests for hermes_tui.tools module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from hermes_tui.tools import (
    MAX_FILE_SIZE,
    ToolRegistry,
    get_time,
    read_file,
    register_builtin_tools,
    write_file,
)


class TestToolRegistry:
    """Tests for the ToolRegistry class."""

    def test_register_tool(self) -> None:
        """A tool registered by name should be retrievable."""
        registry = ToolRegistry()

        def my_tool(x: str) -> str:
            """Do something."""
            return x

        registry.register(my_tool, name="my_tool", description="A test tool")
        assert "my_tool" in registry
        meta = registry.get("my_tool")
        assert meta is not None
        assert meta["name"] == "my_tool"
        assert meta["description"] == "A test tool"

    def test_tool_schema_generation(self) -> None:
        """Auto-generated schema should follow OpenAI function-calling format."""
        registry = ToolRegistry()

        def greet(name: str, times: int = 1) -> str:
            """Greet someone."""
            return name * times

        registry.register(greet)
        tools = registry.list_tools()
        assert len(tools) == 1
        tool = tools[0]
        assert tool["type"] == "function"
        fn = tool["function"]
        assert fn["name"] == "greet"
        assert fn["description"] == "Greet someone."
        props = fn["parameters"]["properties"]
        assert "name" in props
        assert props["name"]["type"] == "string"
        assert "times" in props
        assert props["times"]["type"] == "integer"
        assert "name" in fn["parameters"]["required"]
        assert "times" not in fn["parameters"]["required"]

    async def test_execute_tool(self) -> None:
        """Executing a registered tool should call its function and return result."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        registry.register(add)
        result = await registry.execute("add", a=3, b=4)
        assert result == "7"

    async def test_execute_unknown_tool(self) -> None:
        """Executing an unregistered tool should return an error string."""
        registry = ToolRegistry()
        result = await registry.execute("nonexistent")
        assert "Error" in result
        assert "nonexistent" in result

    def test_list_tools(self) -> None:
        """list_tools should return all registered tools in schema format."""
        registry = ToolRegistry()

        def tool_a() -> str:
            """Tool A."""
            return "a"

        def tool_b() -> str:
            """Tool B."""
            return "b"

        registry.register(tool_a)
        registry.register(tool_b)
        names = {t["function"]["name"] for t in registry.list_tools()}
        assert names == {"tool_a", "tool_b"}

    async def test_tool_exception_handling(self) -> None:
        """Exceptions inside a tool should be caught and returned as error strings."""
        registry = ToolRegistry()

        def bad_tool() -> str:
            """A tool that always fails."""
            raise RuntimeError("boom")

        registry.register(bad_tool)
        result = await registry.execute("bad_tool")
        assert "Error" in result
        assert "boom" in result

    def test_registry_decorator(self) -> None:
        """register() should work as a decorator and register the function."""
        registry = ToolRegistry()

        @registry.register
        def decorated_tool(msg: str) -> str:
            """A decorated tool."""
            return msg.upper()

        assert "decorated_tool" in registry
        meta = registry.get("decorated_tool")
        assert meta is not None
        assert meta["description"] == "A decorated tool."


class TestGetTime:
    """Tests for the get_time tool."""

    def test_get_time(self) -> None:
        """get_time should return a non-empty time string."""
        result = get_time()
        assert isinstance(result, str)
        assert len(result) > 0
        assert "-" in result


class TestReadFile:
    """Tests for the read_file tool."""

    def test_read_file(self, tmp_path: Path) -> None:
        """read_file should return the file's content."""
        f = tmp_path / "hello.txt"
        f.write_text("Hello, world!", encoding="utf-8")
        result = read_file("hello.txt", workspace=tmp_path)
        assert result == "Hello, world!"

    def test_read_file_not_found(self, tmp_path: Path) -> None:
        """Reading a non-existent file should return an error message."""
        result = read_file("nope.txt", workspace=tmp_path)
        assert "Error" in result
        assert "not found" in result.lower()

    def test_read_file_too_large(self, tmp_path: Path) -> None:
        """Reading a file larger than the limit should return an error."""
        f = tmp_path / "big.bin"
        f.write_bytes(b"x" * (MAX_FILE_SIZE + 10))
        result = read_file("big.bin", workspace=tmp_path)
        assert "Error" in result
        assert "too large" in result.lower()

    def test_read_file_sensitive_path(self, tmp_path: Path) -> None:
        """Reading from a sensitive path should be denied."""
        sensitive_dir = tmp_path / ".ssh"
        sensitive_dir.mkdir()
        (sensitive_dir / "id_rsa").write_text("SECRET", encoding="utf-8")
        result = read_file(".ssh/id_rsa", workspace=tmp_path)
        assert "Error" in result
        assert "sensitive" in result.lower()

    def test_read_file_traversal_attempt(self, tmp_path: Path) -> None:
        """Directory traversal should raise ValueError."""
        with pytest.raises(ValueError):
            read_file("../../../etc/passwd", workspace=tmp_path)


class TestWriteFile:
    """Tests for the write_file tool."""

    def test_write_file(self, tmp_path: Path) -> None:
        """write_file should create the file with the given content."""
        result = write_file("output.txt", "data here", workspace=tmp_path)
        assert "Wrote" in result
        content = (tmp_path / "output.txt").read_text(encoding="utf-8")
        assert content == "data here"

    def test_write_file_creates_subdirs(self, tmp_path: Path) -> None:
        """write_file should create parent directories as needed."""
        write_file("sub/dir/file.txt", "nested", workspace=tmp_path)
        assert (tmp_path / "sub" / "dir" / "file.txt").read_text() == "nested"

    def test_write_file_outside_workspace(self, tmp_path: Path) -> None:
        """Writing outside the workspace should raise ValueError."""
        with pytest.raises(ValueError):
            write_file("../../escape.txt", "data", workspace=tmp_path)


class TestWebSearch:
    """Tests for the web_search tool with mocked HTTP."""

    async def test_web_search_mock(self) -> None:
        """web_search should make an HTTP request and parse results."""
        mock_html = """
        <html><body>
        <a class="result__a" href="#">First Result</a>
        <a class="result__a" href="#">Second Result</a>
        </body></html>
        """
        mock_response = httpx.Response(200, text=mock_html)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            from hermes_tui.tools import web_search

            result = await web_search("test query", num_results=2)

        assert "First Result" in result
        assert "Second Result" in result
        mock_get.assert_awaited_once()

    async def test_web_search_no_results(self) -> None:
        """web_search with no results should return a 'no results' message."""
        mock_response = httpx.Response(
            200, text="<html><body>No results</body></html>"
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            from hermes_tui.tools import web_search

            result = await web_search("obscure query")
        assert "No results" in result


class TestBuiltinTools:
    """Tests verifying built-in tools are registered correctly."""

    def test_builtin_tools_registered(self, tmp_path: Path) -> None:
        """register_builtin_tools should register all expected tools."""
        registry = ToolRegistry(workspace=tmp_path)
        register_builtin_tools(registry)
        names = set(registry.list_names())
        assert "get_time" in names
        assert "read_file" in names
        assert "write_file" in names
        assert "web_search" in names
