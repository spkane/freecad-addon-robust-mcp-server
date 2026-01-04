"""MCP tool implementations for FreeCAD.

This package contains all MCP tool definitions for interacting with FreeCAD.
Tools are organized by category:

- execution: Python code execution tools
- documents: Document management tools
- objects: Object creation and manipulation tools
- partdesign: PartDesign workbench tools
- export: Export functionality tools
- macros: Macro management tools
- view: View and screenshot tools
"""

from freecad_mcp.tools.documents import register_document_tools
from freecad_mcp.tools.execution import register_execution_tools
from freecad_mcp.tools.export import register_export_tools
from freecad_mcp.tools.macros import register_macro_tools
from freecad_mcp.tools.objects import register_object_tools
from freecad_mcp.tools.partdesign import register_partdesign_tools
from freecad_mcp.tools.view import register_view_tools

__all__ = [
    "register_all_tools",
    "register_document_tools",
    "register_execution_tools",
    "register_export_tools",
    "register_macro_tools",
    "register_object_tools",
    "register_partdesign_tools",
    "register_view_tools",
]


def register_all_tools(mcp, get_bridge_func) -> None:
    """Register all FreeCAD tools with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        get_bridge_func: Async function to get the active bridge.
    """
    register_execution_tools(mcp, get_bridge_func)
    register_document_tools(mcp, get_bridge_func)
    register_object_tools(mcp, get_bridge_func)
    register_partdesign_tools(mcp, get_bridge_func)
    register_export_tools(mcp, get_bridge_func)
    register_macro_tools(mcp, get_bridge_func)
    register_view_tools(mcp, get_bridge_func)
