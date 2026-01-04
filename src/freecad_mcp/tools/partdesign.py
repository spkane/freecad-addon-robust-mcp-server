"""PartDesign tools for FreeCAD MCP server.

This module provides tools for the PartDesign workbench, enabling
parametric solid modeling operations like Pad, Pocket, Fillet, etc.

Based on learnings from contextform/freecad-mcp which has the most
comprehensive PartDesign coverage.
"""

from typing import Any


def register_partdesign_tools(mcp, get_bridge) -> None:
    """Register PartDesign-related tools with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        get_bridge: Async function to get the active bridge.
    """

    @mcp.tool()
    async def create_partdesign_body(
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new PartDesign Body.

        A PartDesign Body is a container for feature-based modeling that
        maintains a single solid shape through a sequence of operations.

        Args:
            name: Body name. Auto-generated if None.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created body information:
                - name: Body name
                - label: Body label
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.create_object("PartDesign::Body", name, None, doc_name)
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
        }

    @mcp.tool()
    async def create_sketch(
        body_name: str | None = None,
        plane: str = "XY_Plane",
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new Sketch attached to a plane or body.

        Args:
            body_name: Name of PartDesign Body to attach to. Creates standalone if None.
            plane: Plane to attach sketch to. Options:
                - "XY_Plane" - Horizontal plane
                - "XZ_Plane" - Front vertical plane
                - "YZ_Plane" - Side vertical plane
                - Face name like "Face1" to attach to body face
            name: Sketch name. Auto-generated if None.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created sketch information:
                - name: Sketch name
                - label: Sketch label
                - type_id: Object type
                - support: What the sketch is attached to
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    doc = FreeCAD.newDocument("Unnamed")

sketch_name = {name!r} or "Sketch"

if {body_name!r}:
    body = doc.getObject({body_name!r})
    if body is None:
        raise ValueError(f"Body not found: {body_name!r}")

    # Add sketch to body
    sketch = body.newObject("Sketcher::SketchObject", sketch_name)

    # Set support plane
    plane = {plane!r}
    if plane in ["XY_Plane", "XZ_Plane", "YZ_Plane"]:
        sketch.Support = (body.Origin.getObject(plane), [""])
        sketch.MapMode = "FlatFace"
    elif plane.startswith("Face"):
        # Attach to face
        sketch.Support = (body, [plane])
        sketch.MapMode = "FlatFace"
else:
    # Standalone sketch
    sketch = doc.addObject("Sketcher::SketchObject", sketch_name)

    plane = {plane!r}
    if plane == "XY_Plane":
        sketch.Placement = FreeCAD.Placement(FreeCAD.Vector(0,0,0), FreeCAD.Rotation(0,0,0,1))
    elif plane == "XZ_Plane":
        sketch.Placement = FreeCAD.Placement(FreeCAD.Vector(0,0,0), FreeCAD.Rotation(FreeCAD.Vector(1,0,0), 90))
    elif plane == "YZ_Plane":
        sketch.Placement = FreeCAD.Placement(FreeCAD.Vector(0,0,0), FreeCAD.Rotation(FreeCAD.Vector(0,1,0), 90))

doc.recompute()

_result_ = {{
    "name": sketch.Name,
    "label": sketch.Label,
    "type_id": sketch.TypeId,
    "support": str(sketch.Support) if hasattr(sketch, "Support") else None,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Create sketch failed")

    @mcp.tool()
    async def add_sketch_rectangle(
        sketch_name: str,
        x: float,
        y: float,
        width: float,
        height: float,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Add a rectangle to a sketch.

        Args:
            sketch_name: Name of the sketch to add rectangle to.
            x: X coordinate of bottom-left corner.
            y: Y coordinate of bottom-left corner.
            width: Rectangle width.
            height: Rectangle height.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with geometry info:
                - constraint_count: Number of constraints in sketch
                - geometry_count: Number of geometry elements
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

# Add rectangle
import Part

x, y, w, h = {x}, {y}, {width}, {height}

# Add lines
sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(x, y, 0), FreeCAD.Vector(x+w, y, 0)), False)
sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(x+w, y, 0), FreeCAD.Vector(x+w, y+h, 0)), False)
sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(x+w, y+h, 0), FreeCAD.Vector(x, y+h, 0)), False)
sketch.addGeometry(Part.LineSegment(FreeCAD.Vector(x, y+h, 0), FreeCAD.Vector(x, y, 0)), False)

# Add coincident constraints to close the rectangle
n = sketch.GeometryCount - 4
sketch.addConstraint(Sketcher.Constraint("Coincident", n, 2, n+1, 1))
sketch.addConstraint(Sketcher.Constraint("Coincident", n+1, 2, n+2, 1))
sketch.addConstraint(Sketcher.Constraint("Coincident", n+2, 2, n+3, 1))
sketch.addConstraint(Sketcher.Constraint("Coincident", n+3, 2, n, 1))

doc.recompute()

_result_ = {{
    "constraint_count": sketch.ConstraintCount,
    "geometry_count": sketch.GeometryCount,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Add rectangle failed")

    @mcp.tool()
    async def add_sketch_circle(
        sketch_name: str,
        center_x: float,
        center_y: float,
        radius: float,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Add a circle to a sketch.

        Args:
            sketch_name: Name of the sketch to add circle to.
            center_x: X coordinate of center.
            center_y: Y coordinate of center.
            radius: Circle radius.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with geometry info:
                - geometry_index: Index of the added circle
                - geometry_count: Total geometry elements
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

import Part

idx = sketch.addGeometry(Part.Circle(FreeCAD.Vector({center_x}, {center_y}, 0), FreeCAD.Vector(0,0,1), {radius}), False)
doc.recompute()

_result_ = {{
    "geometry_index": idx,
    "geometry_count": sketch.GeometryCount,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Add circle failed")

    @mcp.tool()
    async def pad_sketch(
        sketch_name: str,
        length: float,
        symmetric: bool = False,
        reversed: bool = False,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Pad (extrusion) from a sketch.

        Args:
            sketch_name: Name of the sketch to pad.
            length: Pad length (extrusion distance).
            symmetric: Whether to extrude symmetrically. Defaults to False.
            reversed: Whether to reverse direction. Defaults to False.
            name: Pad feature name. Auto-generated if None.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with created pad information:
                - name: Pad name
                - label: Pad label
                - type_id: Object type
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

# Find the body containing this sketch
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and sketch in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Sketch must be inside a PartDesign Body for Pad operation")

pad_name = {name!r} or "Pad"
pad = body.newObject("PartDesign::Pad", pad_name)
pad.Profile = sketch
pad.Length = {length}
pad.Symmetric = {symmetric}
pad.Reversed = {reversed}

doc.recompute()

_result_ = {{
    "name": pad.Name,
    "label": pad.Label,
    "type_id": pad.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Pad failed")

    @mcp.tool()
    async def pocket_sketch(
        sketch_name: str,
        length: float,
        type: str = "Length",
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Pocket (cut extrusion) from a sketch.

        Args:
            sketch_name: Name of the sketch to pocket.
            length: Pocket depth.
            type: Pocket type: "Length", "ThroughAll", "UpToFirst", "UpToFace".
            name: Pocket feature name. Auto-generated if None.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with created pocket information:
                - name: Pocket name
                - label: Pocket label
                - type_id: Object type
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

# Find the body containing this sketch
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and sketch in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Sketch must be inside a PartDesign Body for Pocket operation")

pocket_name = {name!r} or "Pocket"
pocket = body.newObject("PartDesign::Pocket", pocket_name)
pocket.Profile = sketch
pocket.Length = {length}
pocket.Type = {type!r}

doc.recompute()

_result_ = {{
    "name": pocket.Name,
    "label": pocket.Label,
    "type_id": pocket.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Pocket failed")

    @mcp.tool()
    async def fillet_edges(
        object_name: str,
        radius: float,
        edges: list[str] | None = None,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Add fillet (rounded edges) to an object.

        Args:
            object_name: Name of the object to fillet.
            radius: Fillet radius.
            edges: List of edge names to fillet (e.g., ["Edge1", "Edge2"]).
                   Fillets all edges if None.
            name: Fillet feature name. Auto-generated if None.
            doc_name: Document containing the object. Uses active document if None.

        Returns:
            Dictionary with created fillet information:
                - name: Fillet name
                - label: Fillet label
                - type_id: Object type
        """
        bridge = await get_bridge()

        edges_str = edges if edges else "None"

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
obj = doc.getObject({object_name!r})
if obj is None:
    raise ValueError(f"Object not found: {object_name!r}")

fillet_name = {name!r} or "Fillet"

# Check if this is in a PartDesign Body
body = None
for parent in doc.Objects:
    if parent.TypeId == "PartDesign::Body":
        if hasattr(parent, "Group") and obj in parent.Group:
            body = parent
            break

if body:
    # PartDesign Fillet
    fillet = body.newObject("PartDesign::Fillet", fillet_name)
    fillet.Base = (obj, {edges_str!r} or obj.Shape.Edges)
    fillet.Radius = {radius}
else:
    # Part Fillet
    fillet = doc.addObject("Part::Fillet", fillet_name)
    fillet.Base = obj

    if {edges_str!r}:
        edge_list = [(int(e.replace("Edge", "")), {radius}, {radius}) for e in {edges_str!r}]
    else:
        edge_list = [(i+1, {radius}, {radius}) for i in range(len(obj.Shape.Edges))]

    fillet.Edges = edge_list

doc.recompute()

_result_ = {{
    "name": fillet.Name,
    "label": fillet.Label,
    "type_id": fillet.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Fillet failed")

    @mcp.tool()
    async def chamfer_edges(
        object_name: str,
        size: float,
        edges: list[str] | None = None,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Add chamfer (beveled edges) to an object.

        Args:
            object_name: Name of the object to chamfer.
            size: Chamfer size.
            edges: List of edge names to chamfer (e.g., ["Edge1", "Edge2"]).
                   Chamfers all edges if None.
            name: Chamfer feature name. Auto-generated if None.
            doc_name: Document containing the object. Uses active document if None.

        Returns:
            Dictionary with created chamfer information:
                - name: Chamfer name
                - label: Chamfer label
                - type_id: Object type
        """
        bridge = await get_bridge()

        edges_str = edges if edges else "None"

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
obj = doc.getObject({object_name!r})
if obj is None:
    raise ValueError(f"Object not found: {object_name!r}")

chamfer_name = {name!r} or "Chamfer"

# Check if this is in a PartDesign Body
body = None
for parent in doc.Objects:
    if parent.TypeId == "PartDesign::Body":
        if hasattr(parent, "Group") and obj in parent.Group:
            body = parent
            break

if body:
    # PartDesign Chamfer
    chamfer = body.newObject("PartDesign::Chamfer", chamfer_name)
    chamfer.Base = (obj, {edges_str!r} or obj.Shape.Edges)
    chamfer.Size = {size}
else:
    # Part Chamfer
    chamfer = doc.addObject("Part::Chamfer", chamfer_name)
    chamfer.Base = obj

    if {edges_str!r}:
        edge_list = [(int(e.replace("Edge", "")), {size}, {size}) for e in {edges_str!r}]
    else:
        edge_list = [(i+1, {size}, {size}) for i in range(len(obj.Shape.Edges))]

    chamfer.Edges = edge_list

doc.recompute()

_result_ = {{
    "name": chamfer.Name,
    "label": chamfer.Label,
    "type_id": chamfer.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Chamfer failed")

    @mcp.tool()
    async def revolution_sketch(
        sketch_name: str,
        angle: float = 360.0,
        axis: str = "Base_X",
        symmetric: bool = False,
        reversed: bool = False,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Revolution (rotational extrusion) from a sketch.

        Revolves the sketch profile around an axis to create a solid of revolution.

        Args:
            sketch_name: Name of the sketch to revolve.
            angle: Revolution angle in degrees. Defaults to 360.
            axis: Axis to revolve around. Options:
                - "Base_X" - X axis
                - "Base_Y" - Y axis
                - "Base_Z" - Z axis
                - "Sketch_V" - Sketch vertical axis
                - "Sketch_H" - Sketch horizontal axis
            symmetric: Whether to revolve symmetrically. Defaults to False.
            reversed: Whether to reverse direction. Defaults to False.
            name: Revolution feature name. Auto-generated if None.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with created revolution information:
                - name: Revolution name
                - label: Revolution label
                - type_id: Object type
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

# Find the body containing this sketch
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and sketch in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Sketch must be inside a PartDesign Body for Revolution operation")

rev_name = {name!r} or "Revolution"
rev = body.newObject("PartDesign::Revolution", rev_name)
rev.Profile = sketch
rev.Angle = {angle}
rev.Symmetric = {symmetric}
rev.Reversed = {reversed}

# Set axis reference
axis_name = {axis!r}
if axis_name.startswith("Base_"):
    axis_ref = axis_name.replace("Base_", "")
    rev.ReferenceAxis = (body.Origin.getObject(f"{{axis_ref}}_Axis"), [""])
elif axis_name.startswith("Sketch_"):
    if axis_name == "Sketch_V":
        rev.ReferenceAxis = (sketch, ["V_Axis"])
    else:
        rev.ReferenceAxis = (sketch, ["H_Axis"])

doc.recompute()

_result_ = {{
    "name": rev.Name,
    "label": rev.Label,
    "type_id": rev.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Revolution failed")

    @mcp.tool()
    async def groove_sketch(
        sketch_name: str,
        angle: float = 360.0,
        axis: str = "Base_X",
        symmetric: bool = False,
        reversed: bool = False,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Groove (subtractive revolution) from a sketch.

        Revolves a sketch profile and subtracts it from existing material.

        Args:
            sketch_name: Name of the sketch to revolve.
            angle: Groove angle in degrees. Defaults to 360.
            axis: Axis to revolve around. Options:
                - "Base_X" - X axis
                - "Base_Y" - Y axis
                - "Base_Z" - Z axis
                - "Sketch_V" - Sketch vertical axis
                - "Sketch_H" - Sketch horizontal axis
            symmetric: Whether to revolve symmetrically. Defaults to False.
            reversed: Whether to reverse direction. Defaults to False.
            name: Groove feature name. Auto-generated if None.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with created groove information:
                - name: Groove name
                - label: Groove label
                - type_id: Object type
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

# Find the body containing this sketch
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and sketch in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Sketch must be inside a PartDesign Body for Groove operation")

groove_name = {name!r} or "Groove"
groove = body.newObject("PartDesign::Groove", groove_name)
groove.Profile = sketch
groove.Angle = {angle}
groove.Symmetric = {symmetric}
groove.Reversed = {reversed}

# Set axis reference
axis_name = {axis!r}
if axis_name.startswith("Base_"):
    axis_ref = axis_name.replace("Base_", "")
    groove.ReferenceAxis = (body.Origin.getObject(f"{{axis_ref}}_Axis"), [""])
elif axis_name.startswith("Sketch_"):
    if axis_name == "Sketch_V":
        groove.ReferenceAxis = (sketch, ["V_Axis"])
    else:
        groove.ReferenceAxis = (sketch, ["H_Axis"])

doc.recompute()

_result_ = {{
    "name": groove.Name,
    "label": groove.Label,
    "type_id": groove.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Groove failed")

    @mcp.tool()
    async def create_hole(
        sketch_name: str,
        diameter: float = 6.0,
        depth: float = 10.0,
        hole_type: str = "Dimension",
        threaded: bool = False,
        thread_type: str = "ISO",
        thread_size: str = "M6",
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Hole feature from a sketch containing point(s).

        Creates parametric holes with optional threading. The sketch should
        contain points defining hole center locations.

        Args:
            sketch_name: Name of the sketch with hole center point(s).
            diameter: Hole diameter (for non-threaded). Defaults to 6.0.
            depth: Hole depth. Defaults to 10.0.
            hole_type: Hole depth type. Options:
                - "Dimension" - Specific depth
                - "ThroughAll" - Through entire part
                - "UpToFirst" - Up to first face
            threaded: Whether hole is threaded. Defaults to False.
            thread_type: Thread standard. Options: "ISO", "UNC", "UNF".
            thread_size: Thread size (e.g., "M6", "M8", "#10", "1/4").
            name: Hole feature name. Auto-generated if None.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with created hole information:
                - name: Hole name
                - label: Hole label
                - type_id: Object type
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

# Find the body containing this sketch
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and sketch in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Sketch must be inside a PartDesign Body for Hole operation")

hole_name = {name!r} or "Hole"
hole = body.newObject("PartDesign::Hole", hole_name)
hole.Profile = sketch
hole.Depth = {depth}

# Set hole type
hole_type = {hole_type!r}
if hole_type == "ThroughAll":
    hole.DepthType = 1
elif hole_type == "UpToFirst":
    hole.DepthType = 2
else:
    hole.DepthType = 0  # Dimension

# Set threading
if {threaded}:
    hole.Threaded = True
    hole.ThreadType = {thread_type!r}
    hole.ThreadSize = {thread_size!r}
else:
    hole.Threaded = False
    hole.Diameter = {diameter}

doc.recompute()

_result_ = {{
    "name": hole.Name,
    "label": hole.Label,
    "type_id": hole.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Hole creation failed")

    @mcp.tool()
    async def linear_pattern(
        feature_name: str,
        direction: str = "X",
        length: float = 50.0,
        occurrences: int = 3,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Linear Pattern from a PartDesign feature.

        Repeats a feature in a linear direction.

        Args:
            feature_name: Name of the feature to pattern.
            direction: Pattern direction. Options: "X", "Y", "Z".
            length: Total pattern length. Defaults to 50.0.
            occurrences: Number of pattern instances. Defaults to 3.
            name: Pattern feature name. Auto-generated if None.
            doc_name: Document containing the feature. Uses active document if None.

        Returns:
            Dictionary with created pattern information:
                - name: Pattern name
                - label: Pattern label
                - type_id: Object type
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
feature = doc.getObject({feature_name!r})
if feature is None:
    raise ValueError(f"Feature not found: {feature_name!r}")

# Find the body containing this feature
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and feature in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Feature must be inside a PartDesign Body")

pattern_name = {name!r} or "LinearPattern"
pattern = body.newObject("PartDesign::LinearPattern", pattern_name)
pattern.Originals = [feature]
pattern.Length = {length}
pattern.Occurrences = {occurrences}

# Set direction
dir_name = {direction!r}
pattern.Direction = (body.Origin.getObject(f"{{dir_name}}_Axis"), [""])

doc.recompute()

_result_ = {{
    "name": pattern.Name,
    "label": pattern.Label,
    "type_id": pattern.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Linear pattern failed")

    @mcp.tool()
    async def polar_pattern(
        feature_name: str,
        axis: str = "Z",
        angle: float = 360.0,
        occurrences: int = 6,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Polar (circular) Pattern from a PartDesign feature.

        Repeats a feature around an axis.

        Args:
            feature_name: Name of the feature to pattern.
            axis: Pattern axis. Options: "X", "Y", "Z".
            angle: Total pattern angle. Defaults to 360.0.
            occurrences: Number of pattern instances. Defaults to 6.
            name: Pattern feature name. Auto-generated if None.
            doc_name: Document containing the feature. Uses active document if None.

        Returns:
            Dictionary with created pattern information:
                - name: Pattern name
                - label: Pattern label
                - type_id: Object type
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
feature = doc.getObject({feature_name!r})
if feature is None:
    raise ValueError(f"Feature not found: {feature_name!r}")

# Find the body containing this feature
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and feature in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Feature must be inside a PartDesign Body")

pattern_name = {name!r} or "PolarPattern"
pattern = body.newObject("PartDesign::PolarPattern", pattern_name)
pattern.Originals = [feature]
pattern.Angle = {angle}
pattern.Occurrences = {occurrences}

# Set axis
axis_name = {axis!r}
pattern.Axis = (body.Origin.getObject(f"{{axis_name}}_Axis"), [""])

doc.recompute()

_result_ = {{
    "name": pattern.Name,
    "label": pattern.Label,
    "type_id": pattern.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Polar pattern failed")

    @mcp.tool()
    async def mirrored_feature(
        feature_name: str,
        plane: str = "XY",
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Mirrored feature from a PartDesign feature.

        Mirrors a feature across a plane.

        Args:
            feature_name: Name of the feature to mirror.
            plane: Mirror plane. Options: "XY", "XZ", "YZ".
            name: Mirrored feature name. Auto-generated if None.
            doc_name: Document containing the feature. Uses active document if None.

        Returns:
            Dictionary with created mirror information:
                - name: Mirror name
                - label: Mirror label
                - type_id: Object type
        """
        bridge = await get_bridge()

        plane_map = {
            "XY": "XY_Plane",
            "XZ": "XZ_Plane",
            "YZ": "YZ_Plane",
        }

        if plane not in plane_map:
            raise ValueError(f"Invalid plane: {plane}. Use: XY, XZ, YZ")

        plane_ref = plane_map[plane]

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
feature = doc.getObject({feature_name!r})
if feature is None:
    raise ValueError(f"Feature not found: {feature_name!r}")

# Find the body containing this feature
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and feature in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Feature must be inside a PartDesign Body")

mirror_name = {name!r} or "Mirrored"
mirror = body.newObject("PartDesign::Mirrored", mirror_name)
mirror.Originals = [feature]
mirror.MirrorPlane = (body.Origin.getObject({plane_ref!r}), [""])

doc.recompute()

_result_ = {{
    "name": mirror.Name,
    "label": mirror.Label,
    "type_id": mirror.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Mirrored feature failed")

    @mcp.tool()
    async def add_sketch_line(
        sketch_name: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        construction: bool = False,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Add a line to a sketch.

        Args:
            sketch_name: Name of the sketch to add line to.
            x1: X coordinate of start point.
            y1: Y coordinate of start point.
            x2: X coordinate of end point.
            y2: Y coordinate of end point.
            construction: Whether this is a construction line. Defaults to False.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with geometry info:
                - geometry_index: Index of the added line
                - geometry_count: Total geometry elements
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

import Part

idx = sketch.addGeometry(
    Part.LineSegment(
        FreeCAD.Vector({x1}, {y1}, 0),
        FreeCAD.Vector({x2}, {y2}, 0)
    ),
    {construction}
)
doc.recompute()

_result_ = {{
    "geometry_index": idx,
    "geometry_count": sketch.GeometryCount,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Add line failed")

    @mcp.tool()
    async def add_sketch_arc(
        sketch_name: str,
        center_x: float,
        center_y: float,
        radius: float,
        start_angle: float,
        end_angle: float,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Add an arc to a sketch.

        Args:
            sketch_name: Name of the sketch to add arc to.
            center_x: X coordinate of center.
            center_y: Y coordinate of center.
            radius: Arc radius.
            start_angle: Start angle in degrees.
            end_angle: End angle in degrees.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with geometry info:
                - geometry_index: Index of the added arc
                - geometry_count: Total geometry elements
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

import Part
import math

center = FreeCAD.Vector({center_x}, {center_y}, 0)
start_rad = math.radians({start_angle})
end_rad = math.radians({end_angle})

arc = Part.ArcOfCircle(
    Part.Circle(center, FreeCAD.Vector(0, 0, 1), {radius}),
    start_rad,
    end_rad
)
idx = sketch.addGeometry(arc, False)
doc.recompute()

_result_ = {{
    "geometry_index": idx,
    "geometry_count": sketch.GeometryCount,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Add arc failed")

    @mcp.tool()
    async def add_sketch_point(
        sketch_name: str,
        x: float,
        y: float,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Add a point to a sketch.

        Points are useful for defining hole centers and reference locations.

        Args:
            sketch_name: Name of the sketch to add point to.
            x: X coordinate.
            y: Y coordinate.
            doc_name: Document containing the sketch. Uses active document if None.

        Returns:
            Dictionary with geometry info:
                - geometry_index: Index of the added point
                - geometry_count: Total geometry elements
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
sketch = doc.getObject({sketch_name!r})
if sketch is None:
    raise ValueError(f"Sketch not found: {sketch_name!r}")

import Part

idx = sketch.addGeometry(Part.Point(FreeCAD.Vector({x}, {y}, 0)), False)
doc.recompute()

_result_ = {{
    "geometry_index": idx,
    "geometry_count": sketch.GeometryCount,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Add point failed")

    @mcp.tool()
    async def loft_sketches(
        sketch_names: list[str],
        ruled: bool = False,
        closed: bool = False,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Loft (additive) through multiple sketches.

        A loft creates a solid by connecting multiple profile sketches.

        Args:
            sketch_names: List of sketch names to loft through (in order).
            ruled: Whether to create ruled surfaces. Defaults to False.
            closed: Whether to close the loft. Defaults to False.
            name: Loft feature name. Auto-generated if None.
            doc_name: Document containing the sketches. Uses active document if None.

        Returns:
            Dictionary with created loft information:
                - name: Loft name
                - label: Loft label
                - type_id: Object type
        """
        bridge = await get_bridge()

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})

sketches = []
for sname in {sketch_names!r}:
    sketch = doc.getObject(sname)
    if sketch is None:
        raise ValueError(f"Sketch not found: {{sname}}")
    sketches.append(sketch)

if len(sketches) < 2:
    raise ValueError("Loft requires at least 2 sketches")

# Find the body containing the first sketch
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and sketches[0] in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Sketches must be inside a PartDesign Body for Loft operation")

loft_name = {name!r} or "Loft"
loft = body.newObject("PartDesign::AdditiveLoft", loft_name)
loft.Profile = sketches[0]
loft.Sections = sketches[1:]
loft.Ruled = {ruled}
loft.Closed = {closed}

doc.recompute()

_result_ = {{
    "name": loft.Name,
    "label": loft.Label,
    "type_id": loft.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Loft failed")

    @mcp.tool()
    async def sweep_sketch(
        profile_sketch: str,
        spine_sketch: str,
        transition: str = "Transformed",
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Sweep (additive) along a spine path.

        A sweep extrudes a profile sketch along a path defined by another sketch.

        Args:
            profile_sketch: Name of the profile sketch to sweep.
            spine_sketch: Name of the spine (path) sketch.
            transition: Transition mode. Options:
                - "Transformed" - Smooth transitions
                - "Right" - Sharp corners
                - "Round" - Rounded corners
            name: Sweep feature name. Auto-generated if None.
            doc_name: Document containing the sketches. Uses active document if None.

        Returns:
            Dictionary with created sweep information:
                - name: Sweep name
                - label: Sweep label
                - type_id: Object type
        """
        bridge = await get_bridge()

        transition_map = {
            "Transformed": 0,
            "Right": 1,
            "Round": 2,
        }

        if transition not in transition_map:
            raise ValueError(
                f"Invalid transition: {transition}. Use: Transformed, Right, Round"
            )

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})

profile = doc.getObject({profile_sketch!r})
if profile is None:
    raise ValueError(f"Profile sketch not found: {profile_sketch!r}")

spine = doc.getObject({spine_sketch!r})
if spine is None:
    raise ValueError(f"Spine sketch not found: {spine_sketch!r}")

# Find the body containing the profile sketch
body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        if hasattr(obj, "Group") and profile in obj.Group:
            body = obj
            break

if body is None:
    raise ValueError("Sketches must be inside a PartDesign Body for Sweep operation")

sweep_name = {name!r} or "Sweep"
sweep = body.newObject("PartDesign::AdditivePipe", sweep_name)
sweep.Profile = profile
sweep.Spine = (spine, ["Edge1"])
sweep.Transition = {transition_map[transition]}

doc.recompute()

_result_ = {{
    "name": sweep.Name,
    "label": sweep.Label,
    "type_id": sweep.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Sweep failed")
