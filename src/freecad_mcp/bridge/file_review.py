"""Request-local metadata for model-selected file operations."""

from contextvars import ContextVar
from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

if TYPE_CHECKING:
    from freecad_mcp.bridge.base import ExecutionResult

file_review_target: ContextVar[tuple[str, str, str] | None] = ContextVar(
    "file_review_target", default=None
)
file_review_new_document: ContextVar[bool] = ContextVar(
    "file_review_new_document", default=False
)


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
