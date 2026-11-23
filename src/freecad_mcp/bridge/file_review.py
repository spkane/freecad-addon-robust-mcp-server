"""Request-local metadata for model-selected file operations."""

import asyncio
import contextlib
from contextvars import ContextVar
from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

if TYPE_CHECKING:
    from freecad_mcp.bridge.base import ExecutionResult
    from freecad_mcp.bridge.socket import SocketBridge

file_review_target: ContextVar[tuple[str, str, str] | None] = ContextVar(
    "file_review_target", default=None
)
file_review_document: ContextVar[str | None] = ContextVar(
    "file_review_document", default=None
)
file_review_document_token: ContextVar[str | None] = ContextVar(
    "file_review_document_token", default=None
)
file_review_new_document: ContextVar[bool] = ContextVar(
    "file_review_new_document", default=False
)


async def release_document_reservation(bridge: "SocketBridge", token: str) -> None:
    """Attempt idempotent cleanup even if the invoking task is cancelled."""
    with contextlib.suppress(Exception):
        await asyncio.shield(bridge.release_review_document(token))


def ensure_review_result(result: "ExecutionResult") -> "ExecutionResult":
    """Expose review failures without turning denial into a generic tool error."""
    if result.error_type in {
        "ReviewDenied",
        "ReviewUnavailable",
        "ReviewExecutionUnknown",
        "FileTargetChanged",
    }:
        raise ToolError(f"{result.error_type}: {result.stderr}")
    return result
