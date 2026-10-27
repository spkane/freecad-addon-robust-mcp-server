"""Helpers for registering tools that expose arbitrary code execution."""

from collections.abc import Callable
from typing import Any


def unsafe_tool(mcp: Any, enabled: bool) -> Callable[[Any], Any]:
    """Register a code-execution tool only when the unsafe profile is enabled."""
    if enabled:
        return mcp.tool()
    return lambda function: function
