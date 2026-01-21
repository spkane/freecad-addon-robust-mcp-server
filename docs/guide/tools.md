# Tools Reference

The FreeCAD Robust MCP Server provides 120+ tools for CAD operations. This page provides a quick reference organized by category.

!!! tip "Transaction Support"
    All MCP operations are wrapped in FreeCAD transactions for undo support. After any operation, you can use `undo` to revert changes. This makes it safe for AI agents to experiment and recover from mistakes.

For detailed documentation including parameters and examples, see [MCP Tools Reference](../MCP_TOOLS_REFERENCE.md).

---

## Tool Categories

| Category                                        | Tools | Description                          |
| ----------------------------------------------- | ----- | ------------------------------------ |
| [Execution](#execution-tools)                   | 5     | Python execution, debugging          |
| [Documents](#document-tools)                    | 7     | Document management                  |
| [Primitives](#primitive-tools)                  | 8     | Basic 3D shapes                      |
| [Part Workbench](#part-workbench-tools)         | 30    | Shape creation, operations, queries  |
| [Objects](#object-tools)                        | 12    | Object manipulation                  |
| [PartDesign](#partdesign-tools)                 | 28    | Parametric modeling                  |
| [Sketcher Geometry](#sketcher-geometry-tools)   | 18    | Sketch shapes and operations         |
| [Sketcher Constraints](#sketcher-constraints)   | 17    | Sketch constraints and dimensions    |
| [Validation](#validation-tools)                 | 4     | Object/document health checking      |
| [View & Display](#view-tools)                   | 11    | View control, screenshots (GUI only) |
| [Export/Import](#export-tools)                  | 7     | File format conversion               |
| [Macros](#macro-tools)                          | 6     | Macro management                     |
| [Utility](#utility-tools)                       | 7     | Undo/redo, parts library             |

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

## Part Workbench Tools

The Part workbench provides direct shape creation and manipulation tools using OpenCASCADE geometry.

### Shape Creation

| Tool                 | Description                              |
| -------------------- | ---------------------------------------- |
| `part_make_line`     | Create a line between two points         |
| `part_make_wire`     | Create a wire from connected edges       |
| `part_make_face`     | Create a face from a closed wire         |
| `part_make_shell`    | Create a shell from faces                |
| `part_make_solid`    | Create a solid from a closed shell       |
| `part_make_compound` | Create a compound from multiple shapes   |
| `part_make_polygon`  | Create a polygon wire from points        |
| `part_make_circle`   | Create a circle edge or wire             |
| `part_make_ellipse`  | Create an ellipse edge                   |
| `part_make_b_spline` | Create a B-spline curve from points      |

### Shape Operations

| Tool            | Description                                |
| --------------- | ------------------------------------------ |
| `part_fuse`     | Boolean union (combine shapes)             |
| `part_cut`      | Boolean subtraction (cut one from another) |
| `part_common`   | Boolean intersection (common volume)       |
| `part_fillet`   | Add fillets to shape edges                 |
| `part_chamfer`  | Add chamfers to shape edges                |
| `part_extrude`  | Extrude a shape along a vector             |
| `part_revolve`  | Revolve a shape around an axis             |
| `part_loft`     | Create a loft through multiple profiles    |
| `part_sweep`    | Sweep a profile along a path               |
| `part_offset`   | Create an offset shell of a shape          |
| `part_slice`    | Slice a shape with a plane                 |
| `part_section`  | Create intersection curve of two shapes    |

### Shape Queries

| Tool                      | Description                           |
| ------------------------- | ------------------------------------- |
| `part_check_shape`        | Validate shape geometry               |
| `part_get_faces`          | Get all faces of a shape              |
| `part_get_edges`          | Get all edges of a shape              |
| `part_get_vertices`       | Get all vertices of a shape           |
| `part_measure_distance`   | Measure distance between shapes       |
| `part_measure_angle`      | Measure angle between faces/edges     |
| `part_get_center_of_mass` | Calculate center of mass              |
| `part_get_bounding_box`   | Get axis-aligned bounding box         |

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

### Datum Features

| Tool                             | Description                           |
| -------------------------------- | ------------------------------------- |
| `partdesign_create_datum_point`  | Create a datum point for construction |
| `partdesign_create_datum_line`   | Create a datum line/axis              |
| `partdesign_create_datum_plane`  | Create a datum plane for sketches     |

### Basic Sketch Geometry

| Tool                   | Description             |
| ---------------------- | ----------------------- |
| `add_sketch_rectangle` | Add rectangle to sketch |
| `add_sketch_circle`    | Add circle to sketch    |
| `add_sketch_line`      | Add line to sketch      |
| `add_sketch_arc`       | Add arc to sketch       |
| `add_sketch_point`     | Add point to sketch     |

### Additive Features

| Tool                              | Description                    |
| --------------------------------- | ------------------------------ |
| `pad_sketch`                      | Extrude sketch (additive)      |
| `revolution_sketch`               | Revolve sketch around axis     |
| `loft_sketches`                   | Loft through multiple sketches |
| `sweep_sketch`                    | Sweep profile along path       |
| `partdesign_create_additive_pipe` | Pipe/sweep with auxiliary path |
| `partdesign_create_additive_loft` | Loft with more options         |

### Subtractive Features

| Tool                                 | Description                  |
| ------------------------------------ | ---------------------------- |
| `pocket_sketch`                      | Cut by extruding sketch      |
| `groove_sketch`                      | Cut by revolving sketch      |
| `create_hole`                        | Create parametric holes      |
| `partdesign_create_subtractive_pipe` | Subtractive pipe/sweep       |
| `partdesign_create_subtractive_loft` | Subtractive loft             |

### Dress-up Features

| Tool                          | Description               |
| ----------------------------- | ------------------------- |
| `fillet_edges`                | Add rounded edges         |
| `chamfer_edges`               | Add beveled edges         |
| `partdesign_create_thickness` | Shell/hollow a solid      |
| `partdesign_create_draft`     | Add draft angle to faces  |

### Patterns

| Tool               | Description                 |
| ------------------ | --------------------------- |
| `linear_pattern`   | Repeat feature linearly     |
| `polar_pattern`    | Repeat feature circularly   |
| `mirrored_feature` | Mirror feature across plane |

---

## Sketcher Geometry Tools

Extended sketch geometry and manipulation tools beyond the basic shapes.

### Additional Geometry

| Tool                   | Description                            |
| ---------------------- | -------------------------------------- |
| `sketcher_add_ellipse` | Add ellipse to sketch                  |
| `sketcher_add_b_spline`| Add B-spline curve from control points |
| `sketcher_add_polygon` | Add regular polygon                    |
| `sketcher_add_slot`    | Add slot (rounded rectangle)           |

### Edge Operations

| Tool                    | Description                       |
| ----------------------- | --------------------------------- |
| `sketcher_add_fillet`   | Fillet corner between two lines   |
| `sketcher_add_chamfer`  | Chamfer corner between two lines  |
| `sketcher_trim_curve`   | Trim curve at intersection        |
| `sketcher_extend_curve` | Extend curve to boundary          |
| `sketcher_split_curve`  | Split curve at a point            |
| `sketcher_offset_curve` | Create offset copy of curve       |

### Transformations

| Tool                    | Description                       |
| ----------------------- | --------------------------------- |
| `sketcher_mirror`       | Mirror geometry across axis       |
| `sketcher_array_linear` | Create linear array of geometry   |
| `sketcher_array_polar`  | Create polar array of geometry    |

---

## Sketcher Constraints

Constraints define relationships between sketch geometry elements.

### Geometric Constraints

| Tool                                     | Description                            |
| ---------------------------------------- | -------------------------------------- |
| `sketcher_add_constraint_horizontal`     | Make line horizontal                   |
| `sketcher_add_constraint_vertical`       | Make line vertical                     |
| `sketcher_add_constraint_coincident`     | Make two points coincide               |
| `sketcher_add_constraint_point_on_object`| Place point on line/curve              |
| `sketcher_add_constraint_parallel`       | Make lines parallel                    |
| `sketcher_add_constraint_perpendicular`  | Make lines perpendicular               |
| `sketcher_add_constraint_tangent`        | Make curves tangent                    |
| `sketcher_add_constraint_equal`          | Make lengths/radii equal               |
| `sketcher_add_constraint_symmetric`      | Make points symmetric about a line     |

### Dimensional Constraints

| Tool                               | Description                          |
| ---------------------------------- | ------------------------------------ |
| `sketcher_add_constraint_distance` | Set distance between elements        |
| `sketcher_add_constraint_radius`   | Set circle/arc radius                |
| `sketcher_add_constraint_diameter` | Set circle/arc diameter              |
| `sketcher_add_constraint_angle`    | Set angle between lines              |

### Fix/Lock Constraints

| Tool                            | Description                          |
| ------------------------------- | ------------------------------------ |
| `sketcher_add_constraint_lock`  | Lock point to specific coordinates   |
| `sketcher_add_constraint_block` | Block element from moving            |
| `sketcher_add_constraint_fix`   | Fix point position                   |

### Constraint Management

| Tool                        | Description                          |
| --------------------------- | ------------------------------------ |
| `sketcher_delete_constraint`| Delete a constraint by index         |

---

## Validation Tools

Tools for checking object and document health, with automatic recovery.

| Tool                | Description                                       |
| ------------------- | ------------------------------------------------- |
| `validate_object`   | Check shape validity, error states, recompute     |
| `validate_document` | Check all objects in document, return summary     |
| `undo_if_invalid`   | Validate and auto-undo if invalid objects exist   |
| `safe_execute`      | Execute code with validation and auto-rollback    |

!!! tip "Recovery Pattern"
    Use `undo_if_invalid` after complex operations to automatically recover from failures.

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
