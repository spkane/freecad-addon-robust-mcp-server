"""Helpers for registering tools that expose arbitrary code execution."""

from collections.abc import Awaitable, Callable
from functools import wraps
from inspect import signature
from typing import Any

from mcp.types import ToolAnnotations

from freecad_mcp.bridge.file_review import file_review_target

# File targets are classified explicitly; a missing or ambiguous target must
# never be inferred from arbitrary tool arguments.
_FILE_TARGETS = {
    "open_document": ("path", "read", "path"),
    "save_document": ("path", "write", "path"),
    "import_step": ("file_path", "read", "path"),
    "import_stl": ("file_path", "read", "path"),
    "export_step": ("file_path", "write", "path"),
    "export_stl": ("file_path", "write", "path"),
    "export_3mf": ("file_path", "write", "path"),
    "export_obj": ("file_path", "write", "path"),
    "export_iges": ("file_path", "write", "path"),
    "spreadsheet_import_csv": ("file_path", "read", "path"),
    "spreadsheet_export_csv": ("file_path", "write", "path"),
    "insert_part_from_library": ("part_path", "read", "path"),
    "draft_shapestring": ("font_path", "read", "path"),
    "draft_text_on_surface": ("font_path", "read", "path"),
    "cam_create_job": ("template", "read", "path"),
    "cam_add_tool_controller": ("tool.bit_file", "read", "path"),
    "cam_post_process": ("output_file", "write", "path"),
    "cam_export_job_template": ("file_path", "write", "path"),
    "cam_check_job": ("report_file", "write", "path"),
    "cam_simulate": ("result_file", "write", "path"),
    "cam_import_tool_library": ("file_path", "read", "path"),
    "cam_export_tool_library": ("file_path", "write", "path"),
    "read_macro": ("macro_name", "read", "macro"),
    "delete_macro": ("macro_name", "delete", "macro"),
    "create_macro": ("name", "write", "macro"),
    "create_macro_from_template": ("name", "write", "macro"),
}


def unsafe_tool(mcp: Any, enabled: bool) -> Callable[[Any], Any]:
    """Register a code-execution tool only when the unsafe profile is enabled."""
    if enabled:
        register = mcp.tool(
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=True,
                idempotent_hint=False,
                open_world_hint=True,
            )
        )
        return lambda function: register(_wrap_file_target(function))
    return lambda function: function


def file_tool(
    mcp: Any,
    *,
    read_only: bool = False,
    get_bridge: Callable[[], Awaitable[Any]] | None = None,
) -> Callable[[Any], Any]:
    """Register file tools and identify explicit file targets for review.

    Annotations do not enforce client approval or constrain filesystem access.
    """
    register = mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=read_only,
            destructive_hint=not read_only,
            idempotent_hint=read_only,
            open_world_hint=True,
        )
    )

    return lambda function: register(_wrap_file_target(function, get_bridge))


def _wrap_file_target(
    function: Any, get_bridge: Callable[[], Awaitable[Any]] | None = None
) -> Any:
    target = _FILE_TARGETS.get(function.__name__)
    if target is None:
        return function
    call_signature = signature(function)

    @wraps(function)
    async def reviewed(*args: Any, **kwargs: Any) -> Any:
        bound = call_signature.bind(*args, **kwargs)
        bound.apply_defaults()
        field, *nested = target[0].split(".")
        path = bound.arguments[field]
        for key in nested:
            path = path.get(key) if isinstance(path, dict) else None
        if (
            get_bridge is not None
            and "doc_name" in bound.arguments
            and not bound.arguments["doc_name"]
            and (path or function.__name__ == "cam_create_job")
        ):
            clear_token = file_review_target.set(None)
            try:
                bridge = await get_bridge()
                active = await bridge.get_active_document()
            finally:
                file_review_target.reset(clear_token)
            if active is None:
                raise ValueError("No active document")
            bound.arguments["doc_name"] = active.name
        token = file_review_target.set((path, target[1], target[2]) if path else None)
        try:
            return await function(*bound.args, **bound.kwargs)
        finally:
            file_review_target.reset(token)

    return reviewed
