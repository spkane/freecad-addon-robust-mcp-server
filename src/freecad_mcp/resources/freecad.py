"""FreeCAD Robust MCP resources for exposing FreeCAD state.

This module provides MCP resources that expose FreeCAD's current state
as read-only data. Resources are URI-addressable data that Claude can
access to understand the current FreeCAD environment.

Resource URIs:
    - freecad://capabilities - Complete list of all available tools/resources
    - freecad://version - FreeCAD version information
    - freecad://status - Connection and runtime status
    - freecad://documents - List of open documents
    - freecad://documents/{name} - Single document details
    - freecad://documents/{name}/objects - Objects in a document
    - freecad://objects/{doc_name}/{obj_name} - Object details
    - freecad://active-document - Currently active document
    - freecad://workbenches - Available workbenches
    - freecad://workbenches/active - Currently active workbench
    - freecad://macros - Available macros
    - freecad://console - Recent console output
"""

import json
from typing import Any


def register_resources(mcp: Any, get_bridge: Any) -> None:
    """Register FreeCAD resources with the Robust MCP Server.

    Args:
        mcp: The FastMCP (Robust MCP Server) instance.
        get_bridge: Async function to get the active bridge.
    """

    @mcp.resource("freecad://version")
    async def resource_version() -> str:
        """Get FreeCAD version and build information.

        Returns:
            JSON string containing:
                - version: FreeCAD version string
                - build_date: Build timestamp
                - python_version: Python interpreter version
                - gui_available: Whether GUI mode is active
        """
        bridge = await get_bridge()
        version_info = await bridge.get_freecad_version()
        return json.dumps(version_info, indent=2)

    @mcp.resource("freecad://status")
    async def resource_status() -> str:
        """Get current FreeCAD connection and runtime status.

        Returns:
            JSON string containing:
                - connected: Connection state
                - mode: Bridge mode (embedded, xmlrpc, socket)
                - freecad_version: Version string
                - gui_available: GUI availability
                - last_ping_ms: Connection latency
                - error: Any error message
        """
        bridge = await get_bridge()
        status = await bridge.get_status()
        return json.dumps(
            {
                "connected": status.connected,
                "mode": status.mode,
                "freecad_version": status.freecad_version,
                "gui_available": status.gui_available,
                "last_ping_ms": status.last_ping_ms,
                "error": status.error,
            },
            indent=2,
        )

    @mcp.resource("freecad://documents")
    async def resource_documents() -> str:
        """Get list of all open FreeCAD documents.

        Returns:
            JSON string containing list of documents, each with:
                - name: Internal document name
                - label: Display label
                - path: File path (null if unsaved)
                - object_count: Number of objects
                - is_modified: Has unsaved changes
                - active_object: Currently selected object
        """
        bridge = await get_bridge()
        docs = await bridge.get_documents()
        doc_list = [
            {
                "name": doc.name,
                "label": doc.label,
                "path": doc.path,
                "object_count": len(doc.objects),
                "is_modified": doc.is_modified,
                "active_object": doc.active_object,
            }
            for doc in docs
        ]
        return json.dumps(doc_list, indent=2)

    @mcp.resource("freecad://documents/{name}")
    async def resource_document(name: str) -> str:
        """Get detailed information about a specific document.

        Args:
            name: Document name to query.

        Returns:
            JSON string containing:
                - name: Internal document name
                - label: Display label
                - path: File path (null if unsaved)
                - objects: List of object names
                - is_modified: Has unsaved changes
                - active_object: Currently selected object
        """
        bridge = await get_bridge()
        docs = await bridge.get_documents()

        for doc in docs:
            if doc.name == name:
                return json.dumps(
                    {
                        "name": doc.name,
                        "label": doc.label,
                        "path": doc.path,
                        "objects": doc.objects,
                        "is_modified": doc.is_modified,
                        "active_object": doc.active_object,
                    },
                    indent=2,
                )

        return json.dumps({"error": f"Document '{name}' not found"}, indent=2)

    @mcp.resource("freecad://documents/{name}/objects")
    async def resource_document_objects(name: str) -> str:
        """Get list of objects in a specific document.

        Args:
            name: Document name to query.

        Returns:
            JSON string containing list of objects, each with:
                - name: Object name
                - label: Display label
                - type_id: FreeCAD type identifier
                - visibility: Whether object is visible
        """
        bridge = await get_bridge()
        objects = await bridge.get_objects(doc_name=name)
        obj_list = [
            {
                "name": obj.name,
                "label": obj.label,
                "type_id": obj.type_id,
                "visibility": obj.visibility,
            }
            for obj in objects
        ]
        return json.dumps(obj_list, indent=2)

    @mcp.resource("freecad://objects/{doc_name}/{obj_name}")
    async def resource_object(doc_name: str, obj_name: str) -> str:
        """Get detailed information about a specific object.

        Args:
            doc_name: Document containing the object.
            obj_name: Object name to query.

        Returns:
            JSON string containing:
                - name: Object name
                - label: Display label
                - type_id: FreeCAD type identifier
                - properties: Dictionary of property values
                - shape_info: Shape geometry (if applicable)
                - children: Dependent object names
                - parents: Parent object names
                - visibility: Display visibility
        """
        bridge = await get_bridge()
        obj = await bridge.get_object(obj_name, doc_name=doc_name)

        # Filter properties to only include serializable values
        safe_properties = _make_json_safe(obj.properties)

        return json.dumps(
            {
                "name": obj.name,
                "label": obj.label,
                "type_id": obj.type_id,
                "properties": safe_properties,
                "shape_info": obj.shape_info,
                "children": obj.children,
                "parents": obj.parents,
                "visibility": obj.visibility,
            },
            indent=2,
        )

    @mcp.resource("freecad://workbenches")
    async def resource_workbenches() -> str:
        """Get list of available FreeCAD workbenches.

        Returns:
            JSON string containing list of workbenches, each with:
                - name: Workbench internal name
                - label: Display label
                - is_active: Whether currently active
        """
        bridge = await get_bridge()
        workbenches = await bridge.get_workbenches()
        wb_list = [
            {
                "name": wb.name,
                "label": wb.label,
                "is_active": wb.is_active,
            }
            for wb in workbenches
        ]
        return json.dumps(wb_list, indent=2)

    @mcp.resource("freecad://workbenches/active")
    async def resource_active_workbench() -> str:
        """Get the currently active workbench.

        Returns:
            JSON string containing active workbench info or null.
        """
        bridge = await get_bridge()
        workbenches = await bridge.get_workbenches()
        for wb in workbenches:
            if wb.is_active:
                return json.dumps(
                    {
                        "name": wb.name,
                        "label": wb.label,
                    },
                    indent=2,
                )
        return json.dumps(None)

    @mcp.resource("freecad://macros")
    async def resource_macros() -> str:
        """Get list of available FreeCAD macros.

        Returns:
            JSON string containing list of macros, each with:
                - name: Macro name (without extension)
                - path: Full file path
                - description: Macro description
                - is_system: Whether it's a system macro
        """
        bridge = await get_bridge()
        macros = await bridge.get_macros()
        macro_list = [
            {
                "name": macro.name,
                "path": macro.path,
                "description": macro.description,
                "is_system": macro.is_system,
            }
            for macro in macros
        ]
        return json.dumps(macro_list, indent=2)

    @mcp.resource("freecad://console")
    async def resource_console() -> str:
        """Get recent FreeCAD console output.

        Returns:
            JSON string containing:
                - lines: List of console output lines
                - count: Number of lines
        """
        bridge = await get_bridge()
        lines = await bridge.get_console_output(lines=100)
        return json.dumps(
            {
                "lines": lines,
                "count": len(lines),
            },
            indent=2,
        )

    @mcp.resource("freecad://active-document")
    async def resource_active_document() -> str:
        """Get the currently active document.

        Returns:
            JSON string containing active document info or null.
        """
        bridge = await get_bridge()
        doc = await bridge.get_active_document()
        if doc is None:
            return json.dumps(None)
        return json.dumps(
            {
                "name": doc.name,
                "label": doc.label,
                "path": doc.path,
                "objects": doc.objects,
                "is_modified": doc.is_modified,
                "active_object": doc.active_object,
            },
            indent=2,
        )

    @mcp.resource("freecad://capabilities")
    async def resource_capabilities() -> str:
        """Get comprehensive list of all MCP capabilities.

        This resource provides a complete catalog of all available tools,
        resources, and prompts. Use this to discover what functionality
        is available when working with the FreeCAD Robust MCP Server.

        Returns:
            JSON string containing:
                - tools: Dict of tool categories with tool definitions
                - resources: List of available resource URIs
                - prompts: List of available prompt names
                - examples: Common usage patterns
        """
        capabilities = {
            "description": "FreeCAD Robust MCP Server - Control FreeCAD via Model Context Protocol",
            "tools": {
                "execution": {
                    "description": "Execute Python code and access console",
                    "tools": [
                        {
                            "name": "execute_python",
                            "description": "Execute arbitrary Python code in FreeCAD's context. Use _result_ = value to return data.",
                            "key_params": ["code", "timeout_ms"],
                        },
                        {
                            "name": "get_console_output",
                            "description": "Get recent FreeCAD console output for debugging",
                            "key_params": ["lines"],
                        },
                        {
                            "name": "get_console_log",
                            "description": "Alternative console log access",
                            "key_params": ["lines"],
                        },
                        {
                            "name": "get_freecad_version",
                            "description": "Get FreeCAD version, build date, Python version",
                            "key_params": [],
                        },
                        {
                            "name": "get_connection_status",
                            "description": "Check MCP bridge connection status and latency",
                            "key_params": [],
                        },
                        {
                            "name": "get_mcp_server_environment",
                            "description": "Get Robust MCP Server environment info (instance_id, OS, hostname, FreeCAD connection)",
                            "key_params": [],
                        },
                    ],
                },
                "documents": {
                    "description": "Document management",
                    "tools": [
                        {
                            "name": "list_documents",
                            "description": "List all open FreeCAD documents",
                            "key_params": [],
                        },
                        {
                            "name": "get_active_document",
                            "description": "Get info about currently active document",
                            "key_params": [],
                        },
                        {
                            "name": "create_document",
                            "description": "Create a new FreeCAD document",
                            "key_params": ["name"],
                        },
                        {
                            "name": "open_document",
                            "description": "Open an existing .FCStd file",
                            "key_params": ["path"],
                        },
                        {
                            "name": "save_document",
                            "description": "Save document to disk",
                            "key_params": ["doc_name", "path"],
                        },
                        {
                            "name": "close_document",
                            "description": "Close a document",
                            "key_params": ["doc_name"],
                        },
                        {
                            "name": "recompute_document",
                            "description": "Force recomputation of document features",
                            "key_params": ["doc_name"],
                        },
                    ],
                },
                "objects": {
                    "description": "Object creation and manipulation",
                    "tools": [
                        {
                            "name": "list_objects",
                            "description": "List all objects in a document",
                            "key_params": ["doc_name"],
                        },
                        {
                            "name": "inspect_object",
                            "description": "Get detailed info about an object",
                            "key_params": ["object_name", "doc_name"],
                        },
                        {
                            "name": "create_box",
                            "description": "Create Part::Box primitive",
                            "key_params": ["length", "width", "height"],
                        },
                        {
                            "name": "create_cylinder",
                            "description": "Create Part::Cylinder primitive",
                            "key_params": ["radius", "height"],
                        },
                        {
                            "name": "create_sphere",
                            "description": "Create Part::Sphere primitive",
                            "key_params": ["radius"],
                        },
                        {
                            "name": "create_cone",
                            "description": "Create Part::Cone primitive",
                            "key_params": ["radius1", "radius2", "height"],
                        },
                        {
                            "name": "create_torus",
                            "description": "Create Part::Torus primitive",
                            "key_params": ["radius1", "radius2"],
                        },
                        {
                            "name": "boolean_operation",
                            "description": "Union, cut, or intersection operations",
                            "key_params": ["operation", "object1", "object2"],
                        },
                        {
                            "name": "edit_object",
                            "description": "Modify object properties",
                            "key_params": ["object_name", "properties"],
                        },
                        {
                            "name": "delete_object",
                            "description": "Delete an object",
                            "key_params": ["object_name"],
                        },
                        {
                            "name": "set_placement",
                            "description": "Set object position and rotation",
                            "key_params": ["object_name", "x", "y", "z"],
                        },
                        {
                            "name": "copy_object",
                            "description": "Create a copy of an object",
                            "key_params": ["object_name"],
                        },
                        {
                            "name": "mirror_object",
                            "description": "Mirror object across a plane",
                            "key_params": ["object_name", "plane"],
                        },
                    ],
                },
                "selection": {
                    "description": "Selection management",
                    "tools": [
                        {
                            "name": "get_selection",
                            "description": "Get currently selected objects",
                            "key_params": ["doc_name"],
                        },
                        {
                            "name": "set_selection",
                            "description": "Select specific objects",
                            "key_params": ["object_names"],
                        },
                        {
                            "name": "clear_selection",
                            "description": "Clear current selection",
                            "key_params": [],
                        },
                    ],
                },
                "partdesign": {
                    "description": "Parametric modeling with PartDesign workbench",
                    "tools": [
                        {
                            "name": "create_partdesign_body",
                            "description": "Create a PartDesign::Body container",
                            "key_params": ["name"],
                        },
                        {
                            "name": "create_sketch",
                            "description": "Create sketch on plane or face",
                            "key_params": ["body_name", "plane"],
                        },
                        {
                            "name": "add_sketch_rectangle",
                            "description": "Add rectangle to sketch",
                            "key_params": ["sketch_name", "x", "y", "width", "height"],
                        },
                        {
                            "name": "add_sketch_circle",
                            "description": "Add circle to sketch",
                            "key_params": ["sketch_name", "x", "y", "radius"],
                        },
                        {
                            "name": "add_sketch_line",
                            "description": "Add line to sketch",
                            "key_params": ["sketch_name", "x1", "y1", "x2", "y2"],
                        },
                        {
                            "name": "add_sketch_arc",
                            "description": "Add arc to sketch",
                            "key_params": [
                                "sketch_name",
                                "center_x",
                                "center_y",
                                "radius",
                            ],
                        },
                        {
                            "name": "add_sketch_point",
                            "description": "Add point to sketch (for holes)",
                            "key_params": ["sketch_name", "x", "y"],
                        },
                        {
                            "name": "pad_sketch",
                            "description": "Extrude sketch (additive)",
                            "key_params": ["body_name", "sketch_name", "length"],
                        },
                        {
                            "name": "pocket_sketch",
                            "description": "Cut using sketch (subtractive)",
                            "key_params": ["body_name", "sketch_name", "length"],
                        },
                        {
                            "name": "revolution_sketch",
                            "description": "Revolve sketch around axis",
                            "key_params": ["body_name", "sketch_name", "axis", "angle"],
                        },
                        {
                            "name": "create_hole",
                            "description": "Create parametric hole feature",
                            "key_params": [
                                "body_name",
                                "sketch_name",
                                "diameter",
                                "depth",
                            ],
                        },
                        {
                            "name": "fillet_edges",
                            "description": "Add fillets to edges",
                            "key_params": ["body_name", "edges", "radius"],
                        },
                        {
                            "name": "chamfer_edges",
                            "description": "Add chamfers to edges",
                            "key_params": ["body_name", "edges", "size"],
                        },
                        {
                            "name": "loft_sketches",
                            "description": "Create loft between sketches",
                            "key_params": ["body_name", "sketch_names"],
                        },
                        {
                            "name": "sweep_sketch",
                            "description": "Sweep sketch along path",
                            "key_params": [
                                "body_name",
                                "profile_sketch",
                                "path_sketch",
                            ],
                        },
                    ],
                },
                "patterns": {
                    "description": "Pattern and transform features",
                    "tools": [
                        {
                            "name": "linear_pattern",
                            "description": "Create linear pattern",
                            "key_params": [
                                "body_name",
                                "feature_name",
                                "direction",
                                "count",
                            ],
                        },
                        {
                            "name": "polar_pattern",
                            "description": "Create circular/polar pattern",
                            "key_params": [
                                "body_name",
                                "feature_name",
                                "axis",
                                "count",
                            ],
                        },
                        {
                            "name": "mirrored_feature",
                            "description": "Mirror feature across plane",
                            "key_params": ["body_name", "feature_name", "plane"],
                        },
                    ],
                },
                "view": {
                    "description": "View and GUI control (some require GUI mode)",
                    "tools": [
                        {
                            "name": "get_screenshot",
                            "description": "Capture 3D view screenshot (GUI only)",
                            "key_params": ["file_path", "width", "height"],
                        },
                        {
                            "name": "set_view_angle",
                            "description": "Set camera to standard views",
                            "key_params": ["angle"],
                        },
                        {
                            "name": "fit_all",
                            "description": "Zoom to fit all objects",
                            "key_params": [],
                        },
                        {
                            "name": "zoom_in",
                            "description": "Zoom in",
                            "key_params": ["factor"],
                        },
                        {
                            "name": "zoom_out",
                            "description": "Zoom out",
                            "key_params": ["factor"],
                        },
                        {
                            "name": "set_object_visibility",
                            "description": "Show/hide objects (GUI only)",
                            "key_params": ["object_name", "visible"],
                        },
                        {
                            "name": "set_display_mode",
                            "description": "Set display mode (wireframe, shaded)",
                            "key_params": ["object_name", "mode"],
                        },
                        {
                            "name": "set_object_color",
                            "description": "Change object color (GUI only)",
                            "key_params": ["object_name", "r", "g", "b"],
                        },
                        {
                            "name": "list_workbenches",
                            "description": "List available workbenches",
                            "key_params": [],
                        },
                        {
                            "name": "activate_workbench",
                            "description": "Switch workbench",
                            "key_params": ["workbench_name"],
                        },
                        {
                            "name": "recompute",
                            "description": "Recompute document",
                            "key_params": ["doc_name"],
                        },
                    ],
                },
                "undo_redo": {
                    "description": "Undo/redo operations",
                    "tools": [
                        {
                            "name": "undo",
                            "description": "Undo last operation",
                            "key_params": ["doc_name"],
                        },
                        {
                            "name": "redo",
                            "description": "Redo undone operation",
                            "key_params": ["doc_name"],
                        },
                        {
                            "name": "get_undo_redo_status",
                            "description": "Get available undo/redo operations",
                            "key_params": ["doc_name"],
                        },
                    ],
                },
                "export_import": {
                    "description": "File export and import",
                    "tools": [
                        {
                            "name": "export_step",
                            "description": "Export to STEP format",
                            "key_params": ["object_names", "file_path"],
                        },
                        {
                            "name": "export_stl",
                            "description": "Export to STL format (3D printing)",
                            "key_params": ["object_names", "file_path"],
                        },
                        {
                            "name": "export_3mf",
                            "description": "Export to 3MF format",
                            "key_params": ["object_names", "file_path"],
                        },
                        {
                            "name": "export_obj",
                            "description": "Export to OBJ format",
                            "key_params": ["object_names", "file_path"],
                        },
                        {
                            "name": "export_iges",
                            "description": "Export to IGES format",
                            "key_params": ["object_names", "file_path"],
                        },
                        {
                            "name": "import_step",
                            "description": "Import STEP file",
                            "key_params": ["file_path"],
                        },
                        {
                            "name": "import_stl",
                            "description": "Import STL file",
                            "key_params": ["file_path"],
                        },
                    ],
                },
                "macros": {
                    "description": "Macro management",
                    "tools": [
                        {
                            "name": "list_macros",
                            "description": "List available macros",
                            "key_params": [],
                        },
                        {
                            "name": "run_macro",
                            "description": "Execute a macro",
                            "key_params": ["macro_name"],
                        },
                        {
                            "name": "create_macro",
                            "description": "Create new macro",
                            "key_params": ["macro_name", "code"],
                        },
                        {
                            "name": "read_macro",
                            "description": "Read macro source code",
                            "key_params": ["macro_name"],
                        },
                        {
                            "name": "delete_macro",
                            "description": "Delete a macro",
                            "key_params": ["macro_name"],
                        },
                    ],
                },
                "parts_library": {
                    "description": "Parts library access",
                    "tools": [
                        {
                            "name": "list_parts_library",
                            "description": "List parts in library",
                            "key_params": [],
                        },
                        {
                            "name": "insert_part_from_library",
                            "description": "Insert part from library",
                            "key_params": ["part_path"],
                        },
                    ],
                },
            },
            "resources": [
                {
                    "uri": "freecad://capabilities",
                    "description": "This resource - lists all available capabilities",
                },
                {
                    "uri": "freecad://version",
                    "description": "FreeCAD version and build information",
                },
                {
                    "uri": "freecad://status",
                    "description": "Connection status, mode, GUI availability",
                },
                {
                    "uri": "freecad://documents",
                    "description": "List of all open documents",
                },
                {
                    "uri": "freecad://documents/{name}",
                    "description": "Details of a specific document",
                },
                {
                    "uri": "freecad://documents/{name}/objects",
                    "description": "Objects in a specific document",
                },
                {
                    "uri": "freecad://objects/{doc_name}/{obj_name}",
                    "description": "Detailed object info with properties",
                },
                {
                    "uri": "freecad://active-document",
                    "description": "Currently active document",
                },
                {
                    "uri": "freecad://workbenches",
                    "description": "Available FreeCAD workbenches",
                },
                {
                    "uri": "freecad://workbenches/active",
                    "description": "Currently active workbench",
                },
                {
                    "uri": "freecad://macros",
                    "description": "Available FreeCAD macros",
                },
                {
                    "uri": "freecad://console",
                    "description": "Recent console output (debugging)",
                },
            ],
            "prompts": [
                {
                    "name": "freecad-help",
                    "description": "Get help on FreeCAD Robust MCP capabilities",
                },
                {
                    "name": "create-parametric-part",
                    "description": "Guide for creating parametric parts",
                },
                {
                    "name": "debug-model",
                    "description": "Help debug model issues",
                },
            ],
            "examples": {
                "debug_macro": {
                    "description": "Debug a macro by checking console output",
                    "steps": [
                        "Use get_console_output(lines=50) to see recent errors",
                        "Use execute_python to inspect document state",
                    ],
                },
                "create_simple_part": {
                    "description": "Create a basic parametric part",
                    "steps": [
                        "create_document(name='MyPart')",
                        "create_partdesign_body(name='Body')",
                        "create_sketch(body_name='Body', plane='XY_Plane')",
                        "add_sketch_rectangle(...)",
                        "pad_sketch(...)",
                    ],
                },
                "export_for_printing": {
                    "description": "Export model for 3D printing",
                    "steps": [
                        "export_stl(object_names=['Body'], file_path='...')",
                        "Or export_3mf for color/material support",
                    ],
                },
            },
        }
        return json.dumps(capabilities, indent=2)


def _make_json_safe(obj: Any) -> Any:
    """Convert an object to be JSON serializable.

    Args:
        obj: Object to convert.

    Returns:
        JSON-safe representation of the object.
    """
    if obj is None:
        return None
    if isinstance(obj, str | int | float | bool):
        return obj
    if isinstance(obj, list | tuple):
        return [_make_json_safe(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    # Convert other types to string representation
    return str(obj)
