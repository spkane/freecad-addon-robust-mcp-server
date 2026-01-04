"""MCP resource implementations for FreeCAD.

This package contains all MCP resource definitions for querying FreeCAD state.
Resources provide read-only access to FreeCAD's current state via URI-addressable
endpoints.

Available resources:
    - freecad://version - FreeCAD version information
    - freecad://status - Connection and runtime status
    - freecad://documents - List of open documents
    - freecad://documents/{name} - Single document details
    - freecad://documents/{name}/objects - Objects in a document
    - freecad://objects/{doc_name}/{obj_name} - Object details
    - freecad://workbenches - Available workbenches
    - freecad://workbenches/active - Currently active workbench
    - freecad://macros - Available macros
    - freecad://console - Recent console output
    - freecad://active-document - Currently active document
"""

from freecad_mcp.resources.freecad import register_resources

__all__ = ["register_resources"]
