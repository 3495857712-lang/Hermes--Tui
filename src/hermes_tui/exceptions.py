"""Custom exceptions for Hermes TUI."""

from __future__ import annotations


class HermesError(Exception):
    """Base exception for all Hermes TUI errors."""


class LLMError(HermesError):
    """Base class for LLM-related errors."""


class AuthenticationError(LLMError):
    """Raised when authentication with the LLM provider fails (HTTP 401)."""


class RateLimitError(LLMError):
    """Raised when the LLM provider rate-limits the request (HTTP 429)."""


class BadRequestError(LLMError):
    """Raised when the LLM provider rejects the request (HTTP 400)."""


class ServerError(LLMError):
    """Raised when the LLM provider returns a 5xx error."""


class ConnectionError(LLMError):
    """Raised when the network connection to the LLM provider fails."""


class ToolError(HermesError):
    """Raised when a tool execution fails."""


class ConfigError(HermesError):
    """Raised when configuration is invalid."""
