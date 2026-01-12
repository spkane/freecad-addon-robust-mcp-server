"""FreeCAD Robust MCP prompts for common CAD tasks.

This module provides reusable prompt templates that help Claude
understand FreeCAD concepts and guide users through complex tasks.

Prompt Categories:
    - Design Workflows: Part design, sketching, modeling
    - Export/Import: File format handling
    - Analysis: Shape inspection, validation
    - Macro Development: Scripting guidance
    - Troubleshooting: Common issues and solutions
"""

from typing import Any


def register_prompts(mcp: Any, get_bridge: Any) -> None:  # noqa: ARG001
    """Register FreeCAD prompts with the Robust MCP Server.

    Args:
        mcp: The FastMCP (Robust MCP Server) instance.
        get_bridge: Async function to get the active bridge (unused but kept
            for interface consistency with other register functions).
    """
    # =========================================================================
    # Design Workflow Prompts
    # =========================================================================

    @mcp.prompt()
    async def design_part(
        description: str,
        units: str = "mm",
    ) -> str:
        """Generate a guided workflow for designing a parametric part.

        Use this prompt when a user wants to create a new part from scratch.
        It provides step-by-step guidance for the PartDesign workflow.

        Args:
            description: Natural language description of the desired part.
            units: Unit system to use (mm, cm, m, in).

        Returns:
            Structured prompt guiding through part design.
        """
        return f"""# FreeCAD Part Design Workflow

## Part Description
{description}

## Recommended Approach

### 1. Create a New Document
First, create a new document for this part:
- Use `create_document` with a descriptive name

### 2. Set Up PartDesign Body
Create a PartDesign body to contain the parametric features:
- Use `create_partdesign_body` to create the body container
- This enables the parametric workflow with features

### 3. Create Base Sketch
Design the base profile:
- Use `create_sketch` on the XY plane (or appropriate plane)
- Add geometry with `add_sketch_rectangle`, `add_sketch_circle`, etc.
- Close the sketch when complete

### 4. Extrude the Base
Create the base 3D shape:
- Use `pad_sketch` to extrude the sketch
- Specify length in {units}

### 5. Add Features
Add additional features as needed:
- `pocket_sketch` for cuts/holes
- `fillet_edges` for rounded edges
- `chamfer_edges` for beveled edges

### 6. Verify and Export
When complete:
- Use `inspect_object` to verify dimensions
- Use `get_screenshot` to visualize the result
- Export with `export_step` or `export_stl` as needed

## Units
All dimensions should be specified in **{units}**.
"""

    @mcp.prompt()
    async def create_sketch_guide(
        shape_type: str = "rectangle",
        plane: str = "XY",
    ) -> str:
        """Guide for creating 2D sketches for part design.

        Args:
            shape_type: Type of shape (rectangle, circle, polygon).
            plane: Sketch plane (XY, XZ, YZ).

        Returns:
            Sketch creation guidance.
        """
        return f"""# FreeCAD Sketch Creation Guide

## Target Shape: {shape_type}
## Sketch Plane: {plane}

### Step 1: Create Sketch
Use `create_sketch` with plane="{plane}" to start a new sketch.

### Step 2: Add Geometry

{"#### Rectangle" if shape_type == "rectangle" else ""}
{"Use `add_sketch_rectangle` with:" if shape_type == "rectangle" else ""}
{"- x, y: Starting corner position" if shape_type == "rectangle" else ""}
{"- width, height: Rectangle dimensions" if shape_type == "rectangle" else ""}

{"#### Circle" if shape_type == "circle" else ""}
{"Use `add_sketch_circle` with:" if shape_type == "circle" else ""}
{"- x, y: Center position" if shape_type == "circle" else ""}
{"- radius: Circle radius" if shape_type == "circle" else ""}

{"#### Custom Polygon" if shape_type == "polygon" else ""}
{"Use `execute_python` with Part.makePolygon() for custom shapes." if shape_type == "polygon" else ""}

### Step 3: Constrain the Sketch
For a fully constrained sketch:
- All geometry should have defined positions
- No free degrees of freedom

### Step 4: Close and Use
The sketch can then be:
- Padded (extruded) with `pad_sketch`
- Pocketed (cut) with `pocket_sketch`
- Revolved with `execute_python` using PartDesign Revolution
"""

    @mcp.prompt()
    async def boolean_operations_guide() -> str:
        """Guide for performing boolean operations on shapes.

        Returns:
            Boolean operations guidance.
        """
        return """# FreeCAD Boolean Operations Guide

Boolean operations combine two or more shapes into a new shape.

## Available Operations

### 1. Fuse (Union)
Combines two shapes into one:
```
boolean_operation(
    object1="Box",
    object2="Cylinder",
    operation="fuse",
    result_name="FusedShape"
)
```

### 2. Cut (Difference)
Removes the second shape from the first:
```
boolean_operation(
    object1="Box",
    object2="Cylinder",
    operation="cut",
    result_name="CutShape"
)
```

### 3. Common (Intersection)
Keeps only the overlapping region:
```
boolean_operation(
    object1="Box",
    object2="Cylinder",
    operation="common",
    result_name="CommonShape"
)
```

## Tips
- Shapes must overlap for meaningful results
- The original objects remain in the document
- Use `set_object_visibility` to hide originals after operation
- Recompute the document after boolean operations
"""

    # =========================================================================
    # Export/Import Prompts
    # =========================================================================

    @mcp.prompt()
    async def export_guide(target_format: str = "STEP") -> str:
        """Guide for exporting FreeCAD models to various formats.

        Args:
            target_format: Target export format (STEP, STL, OBJ, IGES).

        Returns:
            Export guidance for the specified format.
        """
        format_info = {
            "STEP": {
                "tool": "export_step",
                "extension": ".step",
                "description": "Standard for exchanging 3D CAD data between systems",
                "best_for": "CAD interchange, preserves geometry precisely",
                "params": "file_path, object_names (optional)",
            },
            "STL": {
                "tool": "export_stl",
                "extension": ".stl",
                "description": "Triangulated mesh format",
                "best_for": "3D printing, mesh-based workflows",
                "params": "file_path, object_names (optional), mesh_tolerance (default 0.1)",
            },
            "OBJ": {
                "tool": "export_obj",
                "extension": ".obj",
                "description": "Wavefront OBJ mesh format",
                "best_for": "3D graphics, rendering, game engines",
                "params": "file_path, object_names (optional)",
            },
            "IGES": {
                "tool": "export_iges",
                "extension": ".iges",
                "description": "Initial Graphics Exchange Specification",
                "best_for": "Legacy CAD systems, surface data",
                "params": "file_path, object_names (optional)",
            },
        }

        info = format_info.get(target_format.upper(), format_info["STEP"])

        return f"""# FreeCAD Export Guide: {target_format.upper()}

## Format: {target_format.upper()} ({info["extension"]})
{info["description"]}

**Best for:** {info["best_for"]}

## Export Command
Use the `{info["tool"]}` tool with parameters:
- {info["params"]}

## Example
```python
{info["tool"]}(
    file_path="/path/to/output{info["extension"]}",
    object_names=["Part1", "Part2"]  # Optional: exports all if not specified
)
```

## Pre-Export Checklist
1. Verify all objects are visible with `list_objects`
2. Check object validity with `inspect_object`
3. Recompute document if needed: `recompute_document`
4. Consider using `fit_all` and `get_screenshot` to verify visually

## Post-Export
- Verify the exported file exists
- Check file size is reasonable
- Test import in target application if possible
"""

    @mcp.prompt()
    async def import_guide(source_format: str = "STEP") -> str:
        """Guide for importing models into FreeCAD.

        Args:
            source_format: Source file format (STEP, STL).

        Returns:
            Import guidance for the specified format.
        """
        format_info = {
            "STEP": {
                "tool": "import_step",
                "description": "Imports precise CAD geometry",
                "notes": "Preserves feature boundaries, faces, and edges",
            },
            "STL": {
                "tool": "import_stl",
                "description": "Imports triangulated mesh",
                "notes": "Results in Mesh object, may need conversion for CAD operations",
            },
        }

        info = format_info.get(source_format.upper(), format_info["STEP"])

        return f"""# FreeCAD Import Guide: {source_format.upper()}

## Format: {source_format.upper()}
{info["description"]}

**Notes:** {info["notes"]}

## Import Command
Use the `{info["tool"]}` tool:
```python
{info["tool"]}(
    file_path="/path/to/file.{source_format.lower()}",
    doc_name="TargetDocument"  # Optional
)
```

## Post-Import Steps
1. List imported objects: `list_objects`
2. Inspect geometry: `inspect_object` on each object
3. Adjust view: `fit_all` to see all imported geometry
4. Take screenshot: `get_screenshot` to verify import

## Common Issues
- Large files may take time to process
- Complex geometry may create many objects
- STL meshes need conversion for boolean operations
"""

    # =========================================================================
    # Analysis Prompts
    # =========================================================================

    @mcp.prompt()
    async def analyze_shape() -> str:
        """Guide for analyzing shape geometry and properties.

        Returns:
            Shape analysis guidance.
        """
        return """# FreeCAD Shape Analysis Guide

## Quick Analysis
Use `inspect_object` with `include_shape=True` to get:
- Volume
- Surface area
- Bounding box
- Vertex/edge/face counts
- Validity status

## Detailed Analysis with Python

### Bounding Box
```python
execute_python('''
obj = FreeCAD.ActiveDocument.getObject("ObjectName")
bb = obj.Shape.BoundBox
_result_ = {
    "min": [bb.XMin, bb.YMin, bb.ZMin],
    "max": [bb.XMax, bb.YMax, bb.ZMax],
    "size": [bb.XLength, bb.YLength, bb.ZLength],
    "center": [bb.Center.x, bb.Center.y, bb.Center.z]
}
''')
```

### Center of Mass
```python
execute_python('''
obj = FreeCAD.ActiveDocument.getObject("ObjectName")
com = obj.Shape.CenterOfMass
_result_ = {"x": com.x, "y": com.y, "z": com.z}
''')
```

### Moments of Inertia
```python
execute_python('''
obj = FreeCAD.ActiveDocument.getObject("ObjectName")
moi = obj.Shape.MatrixOfInertia
_result_ = {
    "Ixx": moi.A11, "Iyy": moi.A22, "Izz": moi.A33,
    "Ixy": moi.A12, "Ixz": moi.A13, "Iyz": moi.A23
}
''')
```

## Validation
Check for geometry issues:
```python
execute_python('''
obj = FreeCAD.ActiveDocument.getObject("ObjectName")
shape = obj.Shape
_result_ = {
    "is_valid": shape.isValid(),
    "is_closed": shape.isClosed() if hasattr(shape, 'isClosed') else None,
    "has_shape": shape.ShapeType != "Compound" or len(shape.Solids) > 0
}
''')
```
"""

    @mcp.prompt()
    async def debug_model() -> str:
        """Guide for debugging FreeCAD model issues.

        Returns:
            Model debugging guidance.
        """
        return """# FreeCAD Model Debugging Guide

## Common Issues and Solutions

### 1. Recompute Errors
**Symptom:** Objects show error state, model doesn't update
**Solution:**
```python
recompute_document()  # Force full recompute
```

### 2. Invalid Shape
**Symptom:** Boolean operations fail, export errors
**Diagnosis:**
```python
execute_python('''
obj = FreeCAD.ActiveDocument.getObject("ObjectName")
_result_ = {
    "valid": obj.Shape.isValid(),
    "type": obj.Shape.ShapeType,
    "check": obj.Shape.check() if hasattr(obj.Shape, 'check') else "N/A"
}
''')
```

### 3. Sketch Not Fully Constrained
**Symptom:** Sketch geometry moves unexpectedly
**Check constraints:**
```python
execute_python('''
sketch = FreeCAD.ActiveDocument.getObject("SketchName")
_result_ = {
    "dof": sketch.solve(),  # Degrees of freedom
    "constraint_count": sketch.ConstraintCount,
    "geometry_count": sketch.GeometryCount
}
''')
```

### 4. Object Dependencies
**Symptom:** Can't delete object, unexpected behavior
**Check dependencies:**
```python
inspect_object("ObjectName")  # Check children and parents
```

### 5. View Not Updating
**Symptom:** Display doesn't match model
**Solution:**
```python
fit_all()  # Reset view
get_screenshot()  # Force view update
```

## Diagnostic Workflow
1. `list_objects` - See all objects and their states
2. `inspect_object` on problematic objects
3. `get_console_output` - Check for error messages
4. `recompute_document` - Force update
5. `get_screenshot` - Visual verification
"""

    # =========================================================================
    # Macro Development Prompts
    # =========================================================================

    @mcp.prompt()
    async def macro_development() -> str:
        """Guide for developing FreeCAD macros.

        Returns:
            Macro development guidance.
        """
        return """# FreeCAD Macro Development Guide

## Macro Structure
A FreeCAD macro is a Python script that automates tasks.

### Basic Template
```python
# -*- coding: utf-8 -*-
# Macro: MacroName
# Description: What the macro does

import FreeCAD
import FreeCADGui

def main():
    # Get active document
    doc = FreeCAD.ActiveDocument
    if doc is None:
        FreeCAD.Console.PrintError("No active document\\n")
        return

    # Your code here

    doc.recompute()
    FreeCAD.Console.PrintMessage("Macro completed\\n")

if __name__ == "__main__":
    main()
```

## Creating a Macro
Use `create_macro` to save a macro:
```python
create_macro(
    name="MyMacro",
    code="... macro code ...",
    description="What it does"
)
```

Or use a template:
```python
create_macro_from_template(
    template_name="part",  # basic, part, sketch, gui, selection
    macro_name="MyPartMacro"
)
```

## Available Templates
- **basic**: Minimal template
- **part**: Part creation with primitives
- **sketch**: 2D sketch operations
- **gui**: GUI interaction with message boxes
- **selection**: Working with selected objects

## Running Macros
```python
run_macro("MacroName")
```

## Best Practices
1. Always check for active document
2. Use FreeCAD.Console for output
3. Call doc.recompute() after changes
4. Handle exceptions gracefully
5. Add descriptive comments
"""

    @mcp.prompt()
    async def python_api_reference() -> str:
        """Quick reference for common FreeCAD Python API operations.

        Returns:
            Python API reference.
        """
        return """# FreeCAD Python API Quick Reference

## Document Operations
```python
# Create/get documents
doc = FreeCAD.newDocument("Name")
doc = FreeCAD.ActiveDocument
doc = FreeCAD.getDocument("Name")

# Document methods
doc.recompute()
doc.save()
doc.saveAs("/path/to/file.FCStd")
```

## Object Operations
```python
# Create objects
box = doc.addObject("Part::Box", "MyBox")
cyl = doc.addObject("Part::Cylinder", "MyCyl")

# Get objects
obj = doc.getObject("ObjectName")
all_objs = doc.Objects

# Modify properties
obj.Length = 100
obj.Placement = FreeCAD.Placement(
    FreeCAD.Vector(x, y, z),
    FreeCAD.Rotation(axis, angle)
)

# Delete
doc.removeObject("ObjectName")
```

## Part Module
```python
import Part

# Primitives
box = Part.makeBox(l, w, h)
cyl = Part.makeCylinder(r, h)
sphere = Part.makeSphere(r)

# Boolean operations
fused = shape1.fuse(shape2)
cut = shape1.cut(shape2)
common = shape1.common(shape2)

# Create from shape
Part.show(shape, "Name")
```

## Sketcher Module
```python
import Sketcher

# Create sketch
sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
sketch.MapMode = "FlatFace"

# Add geometry
sketch.addGeometry(Part.LineSegment(p1, p2))
sketch.addGeometry(Part.Circle(center, normal, radius))

# Add constraints
sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 1, 1, 2))
sketch.addConstraint(Sketcher.Constraint("Horizontal", 0))
```

## GUI Operations
```python
import FreeCADGui as Gui

# View control
view = Gui.ActiveDocument.ActiveView
view.viewIsometric()
view.fitAll()
view.saveImage("/path/to/image.png", 800, 600)

# Object visibility
obj.ViewObject.Visibility = True/False
obj.ViewObject.ShapeColor = (r, g, b)  # 0.0-1.0
```

## Vectors and Placement
```python
# Vector operations
v = FreeCAD.Vector(x, y, z)
v.Length
v.normalize()
v1.cross(v2)
v1.dot(v2)

# Placement
p = FreeCAD.Placement()
p.Base = FreeCAD.Vector(x, y, z)
p.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 45)
```
"""

    # =========================================================================
    # Troubleshooting Prompts
    # =========================================================================

    @mcp.prompt()
    async def troubleshooting() -> str:
        """General troubleshooting guide for FreeCAD Robust MCP.

        Returns:
            Troubleshooting guidance.
        """
        return """# FreeCAD Robust MCP Troubleshooting Guide

## Connection Issues

### Cannot Connect to FreeCAD
1. Verify FreeCAD is running (for socket/xmlrpc modes)
2. Check the MCP plugin is started in FreeCAD
3. Verify port numbers match (default: 9876 socket, 9875 xmlrpc)

**Check status:**
```python
get_connection_status()
```

### Connection Drops
- FreeCAD may be busy with long operations
- Try increasing timeout values
- Check FreeCAD console for errors

## Execution Issues

### Code Execution Timeout
- Increase timeout_ms parameter
- Break complex operations into smaller steps
- Check for infinite loops in code

### No Result Returned
- Ensure you set `_result_ = value` in your code
- Check for exceptions in stderr

**Debug execution:**
```python
execute_python('''
try:
    # Your code
    _result_ = {"success": True, "data": result}
except Exception as e:
    _result_ = {"success": False, "error": str(e)}
''')
```

## GUI Issues

### Screenshots Fail
- Ensure GUI mode is available: `get_freecad_version()`
- Check for active document and view
- Verify view type supports screenshots

### View Not Updating
```python
recompute_document()
fit_all()
```

## Model Issues

### Boolean Operation Fails
- Check shapes are valid
- Ensure shapes overlap
- Try with simpler geometry first

### Export Fails
- Verify objects have valid shapes
- Check file path is writable
- Ensure correct format for geometry type

## Getting Help
1. Check console output: `get_console_output()`
2. Inspect problematic objects: `inspect_object()`
3. Verify document state: `list_documents()`, `list_objects()`
"""
