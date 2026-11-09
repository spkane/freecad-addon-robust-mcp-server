"""Helpers for registering tools that expose arbitrary code execution."""

from collections.abc import Callable
from typing import Any

from mcp.types import ToolAnnotations


def unsafe_tool(mcp: Any, enabled: bool) -> Callable[[Any], Any]:
    """Register a code-execution tool only when the unsafe profile is enabled."""
    if enabled:
        return mcp.tool(
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=True,
                idempotent_hint=False,
                open_world_hint=True,
            )
        )
    return lambda function: function


def file_tool(mcp: Any, *, read_only: bool = False) -> Callable[[Any], Any]:
    """Advertise external file access as advisory risk metadata.

    Annotations do not enforce client approval or constrain filesystem access.
    """
    return mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=read_only,
            destructive_hint=not read_only,
            idempotent_hint=read_only,
            open_world_hint=True,
        )
    )
