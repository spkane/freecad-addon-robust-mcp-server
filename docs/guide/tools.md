# Tools Reference

The FreeCAD Robust MCP Server provides 82+ tools for CAD operations. This page provides a quick reference organized by category.

For detailed documentation including parameters and examples, see [MCP Tools Reference](../MCP_TOOLS_REFERENCE.md).

---

## Tool Categories

| Category                        | Tools | Description                          |
| ------------------------------- | ----- | ------------------------------------ |
| [Execution](#execution-tools)   | 5     | Python execution, debugging          |
| [Documents](#document-tools)    | 7     | Document management                  |
| [Primitives](#primitive-tools)  | 8     | Basic 3D shapes                      |
| [Objects](#object-tools)        | 12    | Object manipulation                  |
| [PartDesign](#partdesign-tools) | 19    | Parametric modeling                  |
| [View & Display](#view-tools)   | 11    | View control, screenshots (GUI only) |
| [Export/Import](#export-tools)  | 7     | File format conversion               |
| [Macros](#macro-tools)          | 6     | Macro management                     |
| [Utility](#utility-tools)       | 7     | Undo/redo, parts library             |

---

## Execution Tools

| Tool                         | Description                                |
| ---------------------------- | ------------------------------------------ |
| `execute_python`             | Execute arbitrary Python in FreeCAD        |
| `get_freecad_version`        | Get FreeCAD version and build info         |
| `get_connection_status`      | Check MCP bridge connection                |
| `get_console_output`         | Get recent console output                  |
| `get_mcp_server_environment` | Get Robust MCP Server environment info     |

---

## Document Tools

| Tool                  | Description                   |
| --------------------- | ----------------------------- |
| `list_documents`      | List all open documents       |
| `get_active_document` | Get currently active document |
| `create_document`     | Create a new document         |
| `open_document`       | Open an existing .FCStd file  |
| `save_document`       | Save a document               |
| `close_document`      | Close a document              |
| `recompute_document`  | Recompute all features        |

---

## Primitive Tools

| Tool              | Description                  |
| ----------------- | ---------------------------- |
| `create_box`      | Create a parametric box      |
| `create_cylinder` | Create a parametric cylinder |
| `create_sphere`   | Create a parametric sphere   |
| `create_cone`     | Create a parametric cone     |
| `create_torus`    | Create a torus (donut)       |
| `create_wedge`    | Create a tapered wedge       |
| `create_helix`    | Create a helix curve         |
| `create_object`   | Create any object by type ID |

---

## Object Tools

| Tool                | Description                      |
| ------------------- | -------------------------------- |
| `list_objects`      | List objects in a document       |
| `inspect_object`    | Get detailed object information  |
| `edit_object`       | Modify object properties         |
| `delete_object`     | Delete an object                 |
| `boolean_operation` | Union, cut, or intersect objects |
| `set_placement`     | Set position and rotation        |
| `rotate_object`     | Rotate around an axis            |
| `scale_object`      | Scale uniformly or non-uniformly |
| `copy_object`       | Create a copy                    |
| `mirror_object`     | Mirror across a plane            |
| `get_selection`     | Get selected objects (GUI)       |
| `set_selection`     | Select objects (GUI)             |
| `clear_selection`   | Clear selection (GUI)            |

---

## PartDesign Tools

### Bodies and Sketches

| Tool                     | Description                     |
| ------------------------ | ------------------------------- |
| `create_partdesign_body` | Create a PartDesign body        |
| `create_sketch`          | Create a sketch on a plane/face |

### Sketch Geometry

| Tool                   | Description             |
| ---------------------- | ----------------------- |
| `add_sketch_rectangle` | Add rectangle to sketch |
| `add_sketch_circle`    | Add circle to sketch    |
| `add_sketch_line`      | Add line to sketch      |
| `add_sketch_arc`       | Add arc to sketch       |
| `add_sketch_point`     | Add point to sketch     |

### Additive Features

| Tool                | Description                    |
| ------------------- | ------------------------------ |
| `pad_sketch`        | Extrude sketch (additive)      |
| `revolution_sketch` | Revolve sketch around axis     |
| `loft_sketches`     | Loft through multiple sketches |
| `sweep_sketch`      | Sweep profile along path       |

### Subtractive Features

| Tool            | Description             |
| --------------- | ----------------------- |
| `pocket_sketch` | Cut by extruding sketch |
| `groove_sketch` | Cut by revolving sketch |
| `create_hole`   | Create parametric holes |

### Edge Operations & Patterns

| Tool               | Description                 |
| ------------------ | --------------------------- |
| `fillet_edges`     | Add rounded edges           |
| `chamfer_edges`    | Add beveled edges           |
| `linear_pattern`   | Repeat feature linearly     |
| `polar_pattern`    | Repeat feature circularly   |
| `mirrored_feature` | Mirror feature across plane |

---

## View Tools

!!! warning "GUI Mode Required"
Tools marked with **GUI** only work when FreeCAD is running in GUI mode.

| Tool                    | Mode | Description                        |
| ----------------------- | ---- | ---------------------------------- |
| `get_screenshot`        | GUI  | Capture 3D view screenshot         |
| `set_view_angle`        | Both | Set camera angle                   |
| `fit_all`               | Both | Fit all objects in view            |
| `zoom_in`               | GUI  | Zoom in                            |
| `zoom_out`              | GUI  | Zoom out                           |
| `set_camera_position`   | GUI  | Set exact camera position          |
| `set_object_visibility` | GUI  | Show/hide objects                  |
| `set_display_mode`      | GUI  | Set display mode (wireframe, etc.) |
| `set_object_color`      | GUI  | Change object color                |
| `list_workbenches`      | Both | List available workbenches         |
| `activate_workbench`    | Both | Switch workbench                   |

---

## Export Tools

| Tool          | Description                        |
| ------------- | ---------------------------------- |
| `export_step` | Export to STEP format              |
| `export_stl`  | Export to STL (3D printing)        |
| `export_3mf`  | Export to 3MF (modern 3D printing) |
| `export_obj`  | Export to OBJ format               |
| `export_iges` | Export to IGES format              |
| `import_step` | Import STEP files                  |
| `import_stl`  | Import STL files                   |

---

## Macro Tools

| Tool                         | Description                     |
| ---------------------------- | ------------------------------- |
| `list_macros`                | List available macros           |
| `run_macro`                  | Execute a macro                 |
| `create_macro`               | Create a new macro              |
| `read_macro`                 | Read macro source code          |
| `delete_macro`               | Delete a user macro             |
| `create_macro_from_template` | Create from predefined template |

---

## Utility Tools

| Tool                       | Description                 |
| -------------------------- | --------------------------- |
| `undo`                     | Undo last operation         |
| `redo`                     | Redo undone operation       |
| `get_undo_redo_status`     | Get undo/redo availability  |
| `recompute`                | Force recompute all objects |
| `get_console_log`          | Get console log with levels |
| `list_parts_library`       | List parts library          |
| `insert_part_from_library` | Insert part from library    |

---

## GUI vs Headless Mode

When running in headless mode, GUI-only tools return structured errors instead of crashing:

```json
{
  "success": false,
  "error": "GUI not available - screenshots cannot be captured in headless mode"
}
```

To check the current mode programmatically:

```python
result = await execute_python("_result_ = FreeCAD.GuiUp")
is_gui_mode = result["result"]
```

---

## Next Steps

- [MCP Tools Reference](../MCP_TOOLS_REFERENCE.md) - Detailed documentation with parameters and examples
- [MCP Resources](resources.md) - Query FreeCAD state via MCP resources
