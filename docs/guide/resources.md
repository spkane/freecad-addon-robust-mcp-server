# MCP Resources

The FreeCAD Robust MCP Server exposes several resources that allow AI assistants to query FreeCAD's state without executing code.

---

## Overview

MCP Resources are read-only endpoints that provide context about FreeCAD's current state. They're useful for:

- Understanding what documents and objects exist
- Getting system information
- Discovering available capabilities

---

## Available Resources

The Robust MCP Server provides 12 resources for querying FreeCAD state:

### freecad://capabilities

Returns a comprehensive JSON catalog of all available tools, resources, and prompts.

**Use case:** Understanding what the Robust MCP Server can do.

**Example response:**

```json
{
  "tools": {
    "execution": ["execute_python", "get_freecad_version", ...],
    "documents": ["create_document", "open_document", ...],
    ...
  },
  "resources": ["freecad://capabilities", "freecad://documents", ...],
  "prompts": ["freecad-help", "create-parametric-part", ...]
}
```

### freecad://version

Gets FreeCAD version and build information.

**Use case:** Checking FreeCAD compatibility and environment.

**Example response:**

```json
{
  "version": "1.0.0",
  "build_date": "2024-01-15",
  "python_version": "3.11.6",
  "gui_available": true
}
```

### freecad://status

Gets current FreeCAD connection and runtime status.

**Use case:** Verifying connection health and mode.

**Example response:**

```json
{
  "connected": true,
  "mode": "xmlrpc",
  "freecad_version": "1.0.0",
  "gui_available": true,
  "last_ping_ms": 12.5,
  "error": null
}
```

### freecad://documents

Lists all open FreeCAD documents with basic information.

**Use case:** Seeing what documents are currently open.

**Example response:**

```json
[
  {
    "name": "MyPart",
    "label": "My Part Design",
    "path": "/home/user/projects/mypart.FCStd",
    "is_modified": true,
    "object_count": 15,
    "active_object": "Pad"
  }
]
```

### freecad://documents/{name}

Gets detailed information about a specific document.

**Use case:** Examining a document's contents.

**Example response:**

```json
{
  "name": "MyPart",
  "label": "My Part Design",
  "path": "/home/user/projects/mypart.FCStd",
  "objects": ["Body", "Sketch", "Pad", "Fillet"],
  "is_modified": true,
  "active_object": "Fillet"
}
```

### freecad://documents/{name}/objects

Gets list of objects in a specific document.

**Use case:** Listing all objects in a document with their types.

**Example response:**

```json
[
  {
    "name": "Body",
    "label": "Body",
    "type_id": "PartDesign::Body",
    "visibility": true
  },
  {
    "name": "Sketch",
    "label": "Sketch",
    "type_id": "Sketcher::SketchObject",
    "visibility": false
  }
]
```

### freecad://objects/{doc_name}/{obj_name}

Gets detailed information about a specific object including properties and shape data.

**Use case:** Inspecting object properties and geometry.

**Example response:**

```json
{
  "name": "Pad",
  "label": "Pad",
  "type_id": "PartDesign::Pad",
  "properties": {
    "Length": 10.0,
    "Type": "Length",
    "Symmetric": false
  },
  "shape_info": {
    "shape_type": "Solid",
    "volume": 1000.0,
    "area": 600.0,
    "is_valid": true
  },
  "children": [],
  "parents": ["Sketch"],
  "visibility": true
}
```

### freecad://active-document

Gets the currently active document.

**Use case:** Quick access to the document the user is working on.

**Example response:**

```json
{
  "name": "MyPart",
  "label": "My Part Design",
  "path": "/home/user/projects/mypart.FCStd",
  "objects": ["Body", "Sketch", "Pad"],
  "is_modified": false,
  "active_object": "Pad"
}
```

### freecad://workbenches

Gets list of available FreeCAD workbenches.

**Use case:** Understanding what workbenches are available.

**Example response:**

```json
[
  {
    "name": "PartDesignWorkbench",
    "label": "Part Design",
    "is_active": true
  },
  {
    "name": "SketcherWorkbench",
    "label": "Sketcher",
    "is_active": false
  }
]
```

### freecad://workbenches/active

Gets the currently active workbench.

**Use case:** Knowing which workbench context is active.

**Example response:**

```json
{
  "name": "PartDesignWorkbench",
  "label": "Part Design"
}
```

### freecad://macros

Gets list of available FreeCAD macros.

**Use case:** Discovering available automation macros.

**Example response:**

```json
[
  {
    "name": "ExportSTL",
    "path": "/home/user/.local/share/FreeCAD/Macro/ExportSTL.FCMacro",
    "description": "Export selected objects to STL",
    "is_system": false
  }
]
```

### freecad://console

Gets recent FreeCAD console output.

**Use case:** Debugging and seeing FreeCAD messages.

**Example response:**

```json
{
  "lines": [
    "MCP Bridge started!",
    "  - XML-RPC: localhost:9875",
    "  - Socket: localhost:9876",
    "Document created: MyPart"
  ],
  "count": 4
}
```

---

## Using Resources in Prompts

When talking to an AI assistant connected via MCP, resources are automatically available. The AI can read them to understand context.

**Example conversation:**

```text
User: "What documents do I have open?"

AI: [Reads freecad://documents resource]
    "You have two documents open:
     1. 'Bracket' - modified, 12 objects
     2. 'Housing' - saved, 8 objects"
```

---

## Resources vs Tools

| Aspect       | Resources               | Tools                |
| ------------ | ----------------------- | -------------------- |
| Purpose      | Query state (read-only) | Perform actions      |
| Side effects | None                    | May modify documents |
| Response     | Data/text               | Operation result     |
| Example      | `freecad://documents`   | `create_document()`  |

---

## Resource URI Summary

| URI                                       | Description                              |
| ----------------------------------------- | ---------------------------------------- |
| `freecad://capabilities`                  | All available tools, resources, prompts  |
| `freecad://version`                       | FreeCAD version and build info           |
| `freecad://status`                        | Connection status and mode               |
| `freecad://documents`                     | List of open documents                   |
| `freecad://documents/{name}`              | Single document details                  |
| `freecad://documents/{name}/objects`      | Objects in a document                    |
| `freecad://objects/{doc_name}/{obj_name}` | Detailed object information              |
| `freecad://active-document`               | Currently active document                |
| `freecad://workbenches`                   | Available workbenches                    |
| `freecad://workbenches/active`            | Currently active workbench               |
| `freecad://macros`                        | Available macros                         |
| `freecad://console`                       | Recent console output                    |

---

## Implementing Custom Resources

If you're extending the Robust MCP Server, you can add custom resources:

```python
@mcp.resource("freecad://custom/{param}")
async def my_custom_resource(param: str) -> str:
    """Return custom data based on param."""
    # Query FreeCAD and return data
    result = await bridge.execute_python(f"...")
    return json.dumps(result)
```

---

## Next Steps

- [Tools Reference](tools.md) - Complete API for MCP tools
- [Connection Modes](connection-modes.md) - How to connect to FreeCAD
