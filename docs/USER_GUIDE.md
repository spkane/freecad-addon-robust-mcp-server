# FreeCAD MCP User Guide

This guide explains how to use AI assistants with FreeCAD via the MCP (Model Context Protocol) server to create and manipulate 3D CAD models.

---

## Table of Contents

1. [Getting Started](#getting-started)
1. [Running Modes](#running-modes)
1. [Basic Workflows](#basic-workflows)
1. [Object Creation Examples](#object-creation-examples)
1. [PartDesign Workflow](#partdesign-workflow)
1. [Complete Example: Mounting Bracket](#complete-example-mounting-bracket)
1. [Tips and Best Practices](#tips-and-best-practices)

---

## Getting Started

### Prerequisites

1. **FreeCAD installed** - Version 1.0.x or later
1. **An MCP client** (Claude Code, or other MCP-compatible AI assistant) configured
1. **Python 3.11** - Must match FreeCAD's bundled Python version

### Starting FreeCAD with MCP Bridge

You have two options depending on your workflow:

#### Headless Mode (Command-line only)

Best for automated workflows, batch processing, or when you don't need visual feedback.

```bash
just freecad::run-headless
```

**Capabilities:** All modeling operations, export, scripting.
**Limitations:** No screenshots, no visual feedback, no color/visibility control.

#### GUI Mode (Full graphical interface)

Best for interactive design work where you want to see results visually.

```bash
just freecad::run-gui
```

**Capabilities:** Everything headless mode can do, plus screenshots, colors, view control.

### Verifying Connection

Once FreeCAD is running with the MCP bridge, you can verify the connection:

```text
"Check the FreeCAD connection status"
```

Claude will use the `get_connection_status` tool to confirm the bridge is working.

---

## Running Modes

### Headless vs GUI Mode

| Feature                  | Headless Mode | GUI Mode |
| ------------------------ | ------------- | -------- |
| Object creation          | Yes           | Yes      |
| Boolean operations       | Yes           | Yes      |
| Export (STEP, STL, etc.) | Yes           | Yes      |
| Save documents           | Yes           | Yes      |
| Screenshots              | No            | Yes      |
| Object colors            | No            | Yes      |
| Object visibility        | No            | Yes      |
| Camera control           | No            | Yes      |
| Interactive selection    | No            | Yes      |

### Detecting the Current Mode

When working with Claude, it will automatically detect whether FreeCAD is in GUI or headless mode and adapt accordingly. GUI-only operations will return informative errors in headless mode rather than crashing.

---

## Basic Workflows

### Creating a Document

Every FreeCAD project needs a document. You can ask Claude:

```text
"Create a new FreeCAD document called 'MyProject'"
```

Claude will use the `create_document` tool.

### Creating Simple Shapes

Ask Claude to create primitive shapes:

```text
"Create a box that's 50mm long, 30mm wide, and 10mm tall"
"Add a cylinder with radius 5mm and height 20mm"
"Create a sphere with 15mm radius"
```

### Positioning Objects

Move and rotate objects:

```text
"Move the box to position (100, 50, 0)"
"Rotate the cylinder 45 degrees around the Z axis"
```

### Boolean Operations

Combine shapes:

```text
"Fuse the box and cylinder together"
"Cut a hole through the box using the cylinder"
"Find the intersection of the two shapes"
```

### Saving and Exporting

```text
"Save the document as MyProject.FCStd"
"Export the model to STEP format"
"Export for 3D printing as STL"
```

---

## Object Creation Examples

### Example 1: Simple Box with Hole

**Request:**

```text
Create a 50x50x20mm box with a 10mm diameter hole through the center.
```

**What Claude does:**

1. Creates a document
1. Creates a box (50x50x20)
1. Creates a cylinder (radius 5, height 30) positioned at center
1. Performs boolean cut operation
1. Returns the result

### Example 2: Pipe/Tube Shape

**Request:**

```text
Create a pipe with outer diameter 40mm, inner diameter 30mm, and length 100mm.
```

**What Claude does:**

1. Creates outer cylinder (radius 20, height 100)
1. Creates inner cylinder (radius 15, height 100)
1. Cuts inner from outer to create hollow tube

### Example 3: L-Bracket

**Request:**

```text
Create an L-shaped bracket:
- Horizontal part: 100mm x 50mm x 5mm
- Vertical part: 5mm x 50mm x 80mm standing on the horizontal part
```

**What Claude does:**

1. Creates horizontal box
1. Creates vertical box positioned at correct location
1. Fuses them together

---

## PartDesign Workflow

For parametric modeling that maintains design history, use the PartDesign workflow.

### Understanding PartDesign Concepts

**Body**: A container for a single solid model built from features.

**Sketch**: A 2D drawing that defines profiles for 3D operations.

**Features**: Operations like Pad (extrude), Pocket (cut), Fillet, etc.

### Basic PartDesign Example

**Request:**

```text
Create a parametric mounting plate:
1. Start with a PartDesign body
2. Create a sketch on the XY plane with a 100x60mm rectangle
3. Pad it 8mm thick
4. Add four 5mm holes near each corner for mounting screws
5. Fillet all edges with 2mm radius
```

**What Claude does:**

1. `create_partdesign_body()` - Creates the Body container
1. `create_sketch(body_name="Body", plane="XY_Plane")` - Creates attached sketch
1. `add_sketch_rectangle(...)` - Adds the profile geometry
1. `pad_sketch(sketch_name="Sketch", length=8)` - Extrudes to solid
1. Creates new sketches with points for hole locations
1. `create_hole(...)` for each mounting hole
1. `fillet_edges(...)` - Rounds the edges

### Revolving Profiles

**Request:**

```text
Create a turned part:
- Draw a profile on the XZ plane
- Revolve it 360 degrees around the X axis
```

**What Claude does:**

1. Creates body and sketch on XZ plane
1. Draws the profile using lines and arcs
1. Uses `revolution_sketch()` to create the solid

### Pattern Operations

**Request:**

```text
Create a plate with a row of 6 holes spaced 15mm apart.
```

**What Claude does:**

1. Creates the base plate
1. Creates one hole feature
1. Uses `linear_pattern()` to repeat the hole

---

## Complete Example: Mounting Bracket

This detailed example shows a complete workflow for creating a practical part.

### Design Requirements

Create a mounting bracket with:

- Base plate: 80mm x 60mm x 5mm
- Vertical support: 5mm thick, 50mm tall, 60mm wide
- Two mounting holes (6mm diameter) on the base
- One slot (10mm x 20mm) on the vertical support
- 3mm fillets on external corners

### Step-by-Step Workflow

#### Step 1: Ask Claude to create the bracket

```text
Create a mounting bracket with the following specifications:

Base plate:
- Size: 80mm x 60mm x 5mm
- Two 6mm diameter mounting holes, centered 15mm from each short edge

Vertical support:
- Attached to one end of the base
- 5mm thick, 60mm wide, 50mm tall
- One slot: 10mm wide x 20mm tall, centered

Finish:
- 3mm fillet on all outer edges
- Export as STEP file when done
```

#### Step 2: Claude's approach

Claude will break this down into manageable operations:

```python
# 1. Create document and PartDesign body
create_document(name="MountingBracket")
create_partdesign_body(name="Body")

# 2. Create base plate sketch and pad
create_sketch(body_name="Body", plane="XY_Plane", name="BaseSketch")
add_sketch_rectangle(sketch_name="BaseSketch", x=0, y=0, width=80, height=60)
pad_sketch(sketch_name="BaseSketch", length=5)

# 3. Add vertical support
create_sketch(body_name="Body", plane="XZ_Plane", name="SupportSketch")
# ... add geometry
pad_sketch(sketch_name="SupportSketch", length=60)

# 4. Add mounting holes
create_sketch(body_name="Body", plane="XY_Plane", name="HoleSketch")
add_sketch_point(sketch_name="HoleSketch", x=15, y=30)
add_sketch_point(sketch_name="HoleSketch", x=65, y=30)
create_hole(sketch_name="HoleSketch", diameter=6, hole_type="ThroughAll")

# 5. Add slot (as pocket)
create_sketch(body_name="Body", plane="Face...", name="SlotSketch")
add_sketch_rectangle(...)
pocket_sketch(sketch_name="SlotSketch", length=5, type="ThroughAll")

# 6. Add fillets
fillet_edges(object_name="...", radius=3)

# 7. Export
export_step(file_path="/path/to/bracket.step")
```

#### Step 3: View the result (GUI mode)

```text
Take a screenshot of the bracket from an isometric view
```

Claude will use `get_screenshot(view_angle="Isometric")` to capture and display the result.

---

## Tips and Best Practices

### 1. Be Specific with Dimensions

**Good:** "Create a box 50mm x 30mm x 10mm"

**Vague:** "Create a small box"

### 2. Specify Units

FreeCAD uses millimeters by default. Always include units to avoid confusion:

```text
"Create a cylinder with 25.4mm (1 inch) diameter"
```

### 3. Use Meaningful Names

```text
"Create a box named 'BasePlate' and a cylinder named 'MountingHole'"
```

This makes it easier to reference objects later.

### 4. Work Incrementally

For complex parts, build step by step:

1. Create the basic shape
1. Verify it looks correct
1. Add features one at a time
1. Check after each major operation

### 5. Save Frequently

```text
"Save the document"
```

FreeCAD can crash, and you don't want to lose work.

### 6. Use PartDesign for Parametric Parts

If you might need to modify dimensions later, use the PartDesign workflow with sketches rather than direct Part operations.

### 7. Export to Multiple Formats

For manufacturing or 3D printing:

```text
"Export as STEP for CNC machining and STL for 3D printing"
```

### 8. Use the execute_python Tool for Advanced Operations

For operations not covered by the standard tools, Claude can execute custom Python:

```text
"Calculate the volume and center of mass of the part"
```

Claude will use `execute_python()` to run the necessary FreeCAD Python commands.

### 9. Check GUI Mode for Visual Features

Before asking for screenshots or colors:

```text
"Is FreeCAD running in GUI mode?"
```

### 10. Use Patterns for Repetitive Features

Instead of creating many individual features:

```text
"Create one hole and pattern it in a 4x3 grid with 20mm spacing"
```

---

## Common Operations Quick Reference

| Task             | How to Ask                                              |
| ---------------- | ------------------------------------------------------- |
| Create box       | "Create a box 50x30x10mm"                               |
| Create cylinder  | "Create a cylinder with 10mm radius and 20mm height"    |
| Move object      | "Move MyBox to position (100, 50, 0)"                   |
| Rotate object    | "Rotate MyCylinder 45 degrees around Z axis"            |
| Boolean union    | "Fuse Box and Cylinder together"                        |
| Boolean subtract | "Cut Cylinder from Box"                                 |
| Create hole      | "Add a 6mm through hole at (25, 15)"                    |
| Fillet edges     | "Add 3mm fillet to all edges"                           |
| Chamfer edges    | "Add 2mm chamfer to selected edges"                     |
| Export STEP      | "Export to STEP format"                                 |
| Export STL       | "Export for 3D printing"                                |
| Save document    | "Save the document as MyPart.FCStd"                     |
| Screenshot       | "Take a screenshot from the front view" (GUI mode only) |
| Change color     | "Make the box red" (GUI mode only)                      |

---

## Troubleshooting

### "GUI not available" Error

You're running in headless mode and trying to use a GUI-only feature. Either:

- Switch to GUI mode: `just freecad::run-gui`
- Use an alternative approach (e.g., skip visual operations)

### Objects Not Appearing

Make sure to recompute the document:

```text
"Recompute the document"
```

### Boolean Operations Failing

Ensure:

1. Both objects have valid shapes
1. The objects actually intersect
1. Objects are in the same document

### Sketch Errors

Sketches need to be fully constrained for PartDesign operations. Ask Claude to:

```text
"Check if the sketch is fully constrained"
```

### Connection Issues

If the MCP bridge isn't responding:

1. Check FreeCAD is running with the bridge started
1. Verify ports 9875 (XML-RPC) and 9876 (socket) are available
1. Restart FreeCAD with `just freecad::run-gui` or `just freecad::run-headless`

---

## Next Steps

- See [MCP_TOOLS_REFERENCE.md](MCP_TOOLS_REFERENCE.md) for detailed API documentation
- Explore the FreeCAD wiki for advanced techniques
- Practice with simple parts before attempting complex assemblies
