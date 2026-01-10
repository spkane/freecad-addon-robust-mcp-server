# Quick Start

Get up and running with AI-assisted FreeCAD modeling in minutes.

---

## Prerequisites

Before starting, ensure you have:

1. FreeCAD installed with the Robust MCP Bridge workbench
1. The MCP server installed (`pip install freecad-robust-mcp`)
1. Your MCP client configured (see [Configuration](configuration.md))

---

## Step 1: Start FreeCAD with the MCP Bridge

### Option A: GUI Mode (Recommended for getting started)

1. Open FreeCAD
1. Switch to the **Robust MCP Bridge** workbench
1. Click **Start Bridge** in the toolbar
1. You should see: "MCP Bridge started! XML-RPC: localhost:9875, Socket: localhost:9876"

### Option B: Headless Mode (For automation)

```bash
# If installed via Addon Manager (Linux)
FreeCADCmd ~/.local/share/FreeCAD/Mod/FreecadRobustMCP/freecad_mcp_bridge/blocking_bridge.py

# If working from source
just freecad::run-headless
```

---

## Step 2: Connect Your AI Assistant

With FreeCAD and the MCP server configured, open your AI assistant (Claude Code, Cursor, etc.) and verify the connection:

```text
"Check the FreeCAD connection status"
```

The AI should respond with information about the connection mode, FreeCAD version, and whether GUI is available.

---

## Step 3: Create Your First Model

Try these example prompts with your AI assistant:

### Simple Box

```text
"Create a new FreeCAD document and add a box that is 20mm x 10mm x 5mm"
```

### Parametric Part with Fillet

```text
"Create a parametric bracket:
1. Start with a 50x30mm rectangular sketch
2. Extrude it 10mm
3. Add a 3mm fillet to all edges"
```

### Export for 3D Printing

```text
"Export the current model to STL format for 3D printing"
```

---

## Step 4: Explore Available Tools

The MCP server provides 82+ tools organized into categories:

| Category   | Examples                                             |
| ---------- | ---------------------------------------------------- |
| Primitives | `create_box`, `create_cylinder`, `create_sphere`     |
| PartDesign | `create_sketch`, `pad_sketch`, `pocket_sketch`       |
| Operations | `boolean_operation`, `fillet_edges`, `chamfer_edges` |
| Export     | `export_stl`, `export_step`, `export_3mf`            |
| View (GUI) | `get_screenshot`, `set_object_color`                 |

See the [Tools Reference](../guide/tools.md) for the complete list.

---

## Example Workflows

### Create a Mounting Bracket

```text
"Help me create a mounting bracket with:
- 60x40mm base plate, 5mm thick
- Two mounting holes (5mm diameter) at the corners
- A vertical wall 30mm tall on one edge
- 2mm fillets on all external edges"
```

### Modify an Existing Model

```text
"Open my_part.FCStd and:
1. List all the objects in the document
2. Change the height of the Pad feature from 10mm to 15mm
3. Save the document"
```

### Debug a Macro

```text
"Read the macro 'MyMacro' and explain what it does.
Then run it and show me any errors."
```

---

## Tips for Effective AI-Assisted Modeling

1. **Be specific about dimensions** - Include units (mm, cm, inches) in your requests
1. **Use parametric approaches** - Ask for PartDesign workflows instead of direct Part operations for parts you'll modify
1. **Check console output** - If something goes wrong, ask the AI to check the FreeCAD console for errors
1. **Take screenshots** - In GUI mode, ask for screenshots to verify the model looks correct
1. **Save frequently** - Ask the AI to save your document after significant changes

---

## Next Steps

- [Tools Reference](../guide/tools.md) - Complete API reference for all tools
- [User Guide](../USER_GUIDE.md) - Detailed workflows and best practices
- [Connection Modes](../guide/connection-modes.md) - Understanding connection modes
