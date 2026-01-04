"""Object management tools for FreeCAD MCP server.

This module provides tools for managing FreeCAD objects:
creating, editing, deleting, and inspecting objects.
"""

from typing import Any


def register_object_tools(mcp, get_bridge) -> None:
    """Register object-related tools with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        get_bridge: Async function to get the active bridge.
    """

    @mcp.tool()
    async def list_objects(doc_name: str | None = None) -> list[dict[str, Any]]:
        """List all objects in a FreeCAD document.

        Args:
            doc_name: Name of document. Uses active document if None.

        Returns:
            List of dictionaries, each containing:
                - name: Object name
                - label: Display label
                - type_id: FreeCAD type identifier (e.g., "Part::Box")
                - visibility: Whether object is visible
        """
        bridge = await get_bridge()
        objects = await bridge.get_objects(doc_name)
        return [
            {
                "name": obj.name,
                "label": obj.label,
                "type_id": obj.type_id,
                "visibility": obj.visibility,
            }
            for obj in objects
        ]

    @mcp.tool()
    async def inspect_object(
        object_name: str,
        doc_name: str | None = None,
        include_properties: bool = True,
        include_shape: bool = True,
    ) -> dict[str, Any]:
        """Get detailed information about a FreeCAD object.

        Args:
            object_name: Name of the object to inspect.
            doc_name: Document containing the object. Uses active document if None.
            include_properties: Whether to include property values.
            include_shape: Whether to include shape geometry details.

        Returns:
            Dictionary containing comprehensive object information:
                - name: Object name
                - label: Object label
                - type_id: FreeCAD type identifier
                - properties: Dictionary of property names and values (if requested)
                - shape_info: Shape details (if requested and object has shape)
                - children: List of child object names
                - parents: List of parent object names
                - visibility: Whether object is visible
        """
        bridge = await get_bridge()
        obj = await bridge.get_object(object_name, doc_name)

        result = {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
            "children": obj.children,
            "parents": obj.parents,
            "visibility": obj.visibility,
        }

        if include_properties:
            result["properties"] = obj.properties

        if include_shape and obj.shape_info:
            result["shape_info"] = obj.shape_info

        return result

    @mcp.tool()
    async def create_object(
        type_id: str,
        name: str | None = None,
        properties: dict[str, Any] | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new FreeCAD object.

        Args:
            type_id: FreeCAD type ID for the object. Common types include:
                - "Part::Box" - Parametric box
                - "Part::Cylinder" - Parametric cylinder
                - "Part::Sphere" - Parametric sphere
                - "Part::Cone" - Parametric cone
                - "Part::Torus" - Parametric torus
                - "Part::Feature" - Generic Part feature
                - "Sketcher::SketchObject" - Sketch
                - "PartDesign::Body" - PartDesign body
            name: Object name. Auto-generated if None.
            properties: Initial property values to set.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created object information:
                - name: Object name
                - label: Object label
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.create_object(type_id, name, properties, doc_name)
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
        }

    @mcp.tool()
    async def create_box(
        length: float = 10.0,
        width: float = 10.0,
        height: float = 10.0,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Part Box primitive.

        Args:
            length: Box length (X dimension). Defaults to 10.0.
            width: Box width (Y dimension). Defaults to 10.0.
            height: Box height (Z dimension). Defaults to 10.0.
            name: Object name. Auto-generated if None.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created object information:
                - name: Object name
                - label: Object label
                - volume: Box volume
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.create_object(
            "Part::Box",
            name,
            {"Length": length, "Width": width, "Height": height},
            doc_name,
        )
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
            "volume": length * width * height,
        }

    @mcp.tool()
    async def create_cylinder(
        radius: float = 5.0,
        height: float = 10.0,
        angle: float = 360.0,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Part Cylinder primitive.

        Args:
            radius: Cylinder radius. Defaults to 5.0.
            height: Cylinder height. Defaults to 10.0.
            angle: Sweep angle in degrees (for partial cylinder). Defaults to 360.
            name: Object name. Auto-generated if None.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created object information:
                - name: Object name
                - label: Object label
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.create_object(
            "Part::Cylinder",
            name,
            {"Radius": radius, "Height": height, "Angle": angle},
            doc_name,
        )
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
        }

    @mcp.tool()
    async def create_sphere(
        radius: float = 5.0,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Part Sphere primitive.

        Args:
            radius: Sphere radius. Defaults to 5.0.
            name: Object name. Auto-generated if None.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created object information:
                - name: Object name
                - label: Object label
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.create_object(
            "Part::Sphere",
            name,
            {"Radius": radius},
            doc_name,
        )
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
        }

    @mcp.tool()
    async def create_cone(
        radius1: float = 5.0,
        radius2: float = 0.0,
        height: float = 10.0,
        angle: float = 360.0,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Part Cone primitive.

        Args:
            radius1: Bottom radius. Defaults to 5.0.
            radius2: Top radius (0 for pointed cone). Defaults to 0.0.
            height: Cone height. Defaults to 10.0.
            angle: Sweep angle in degrees (for partial cone). Defaults to 360.
            name: Object name. Auto-generated if None.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created object information:
                - name: Object name
                - label: Object label
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.create_object(
            "Part::Cone",
            name,
            {"Radius1": radius1, "Radius2": radius2, "Height": height, "Angle": angle},
            doc_name,
        )
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
        }

    @mcp.tool()
    async def create_torus(
        radius1: float = 10.0,
        radius2: float = 2.0,
        angle1: float = -180.0,
        angle2: float = 180.0,
        angle3: float = 360.0,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Part Torus (donut shape) primitive.

        Args:
            radius1: Major radius (center to tube center). Defaults to 10.0.
            radius2: Minor radius (tube radius). Defaults to 2.0.
            angle1: Start angle for tube sweep. Defaults to -180.
            angle2: End angle for tube sweep. Defaults to 180.
            angle3: Rotation angle around axis. Defaults to 360.
            name: Object name. Auto-generated if None.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created object information:
                - name: Object name
                - label: Object label
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.create_object(
            "Part::Torus",
            name,
            {
                "Radius1": radius1,
                "Radius2": radius2,
                "Angle1": angle1,
                "Angle2": angle2,
                "Angle3": angle3,
            },
            doc_name,
        )
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
        }

    @mcp.tool()
    async def create_wedge(
        xmin: float = 0.0,
        ymin: float = 0.0,
        zmin: float = 0.0,
        x2min: float = 2.0,
        z2min: float = 2.0,
        xmax: float = 10.0,
        ymax: float = 10.0,
        zmax: float = 10.0,
        x2max: float = 8.0,
        z2max: float = 8.0,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Part Wedge primitive.

        A wedge is a tapered box shape useful for ramps and similar geometry.

        Args:
            xmin: Minimum X at base. Defaults to 0.0.
            ymin: Minimum Y (base position). Defaults to 0.0.
            zmin: Minimum Z at base. Defaults to 0.0.
            x2min: Minimum X at top. Defaults to 2.0.
            z2min: Minimum Z at top. Defaults to 2.0.
            xmax: Maximum X at base. Defaults to 10.0.
            ymax: Maximum Y (top position). Defaults to 10.0.
            zmax: Maximum Z at base. Defaults to 10.0.
            x2max: Maximum X at top. Defaults to 8.0.
            z2max: Maximum Z at top. Defaults to 8.0.
            name: Object name. Auto-generated if None.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created object information:
                - name: Object name
                - label: Object label
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.create_object(
            "Part::Wedge",
            name,
            {
                "Xmin": xmin,
                "Ymin": ymin,
                "Zmin": zmin,
                "X2min": x2min,
                "Z2min": z2min,
                "Xmax": xmax,
                "Ymax": ymax,
                "Zmax": zmax,
                "X2max": x2max,
                "Z2max": z2max,
            },
            doc_name,
        )
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
        }

    @mcp.tool()
    async def create_helix(
        pitch: float = 5.0,
        height: float = 20.0,
        radius: float = 5.0,
        angle: float = 0.0,
        left_handed: bool = False,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Part Helix curve.

        A helix is a spiral curve, useful as a sweep path for threads and springs.

        Args:
            pitch: Distance between turns. Defaults to 5.0.
            height: Total helix height. Defaults to 20.0.
            radius: Helix radius. Defaults to 5.0.
            angle: Taper angle in degrees. Defaults to 0.0.
            left_handed: Whether helix is left-handed. Defaults to False.
            name: Object name. Auto-generated if None.
            doc_name: Target document. Uses active document if None.

        Returns:
            Dictionary with created object information:
                - name: Object name
                - label: Object label
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.create_object(
            "Part::Helix",
            name,
            {
                "Pitch": pitch,
                "Height": height,
                "Radius": radius,
                "Angle": angle,
                "LocalCoord": 1 if left_handed else 0,
            },
            doc_name,
        )
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
        }

    @mcp.tool()
    async def edit_object(
        object_name: str,
        properties: dict[str, Any],
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Edit properties of an existing FreeCAD object.

        Args:
            object_name: Name of the object to edit.
            properties: Dictionary of property names and new values.
            doc_name: Document containing the object. Uses active document if None.

        Returns:
            Dictionary with updated object information:
                - name: Object name
                - label: Object label
                - type_id: Object type
        """
        bridge = await get_bridge()
        obj = await bridge.edit_object(object_name, properties, doc_name)
        return {
            "name": obj.name,
            "label": obj.label,
            "type_id": obj.type_id,
        }

    @mcp.tool()
    async def delete_object(
        object_name: str,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Delete an object from a FreeCAD document.

        Args:
            object_name: Name of the object to delete.
            doc_name: Document containing the object. Uses active document if None.

        Returns:
            Dictionary with delete result:
                - success: Whether delete was successful
        """
        bridge = await get_bridge()
        await bridge.delete_object(object_name, doc_name)
        return {"success": True}

    @mcp.tool()
    async def boolean_operation(
        operation: str,
        object1_name: str,
        object2_name: str,
        result_name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Perform a boolean operation on two FreeCAD objects.

        Args:
            operation: Boolean operation type: "fuse" (union), "cut" (subtract),
                      or "common" (intersection).
            object1_name: Name of the first object.
            object2_name: Name of the second object.
            result_name: Name for the result object. Auto-generated if None.
            doc_name: Document containing the objects. Uses active document if None.

        Returns:
            Dictionary with result object information:
                - name: Result object name
                - label: Result object label
                - type_id: Result object type
        """
        bridge = await get_bridge()

        operation_map = {
            "fuse": "Part::MultiFuse",
            "cut": "Part::Cut",
            "common": "Part::MultiCommon",
        }

        if operation not in operation_map:
            raise ValueError(f"Invalid operation: {operation}. Use: fuse, cut, common")

        op_type = operation_map[operation]
        result_name = result_name or f"{operation.capitalize()}"

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

obj1 = doc.getObject({object1_name!r})
obj2 = doc.getObject({object2_name!r})

if obj1 is None:
    raise ValueError(f"Object not found: {object1_name!r}")
if obj2 is None:
    raise ValueError(f"Object not found: {object2_name!r}")

if {op_type!r} == "Part::Cut":
    result = doc.addObject({op_type!r}, {result_name!r})
    result.Base = obj1
    result.Tool = obj2
else:
    result = doc.addObject({op_type!r}, {result_name!r})
    result.Shapes = [obj1, obj2]

doc.recompute()

_result_ = {{
    "name": result.Name,
    "label": result.Label,
    "type_id": result.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Boolean operation failed")

    @mcp.tool()
    async def set_placement(
        object_name: str,
        position: list[float] | None = None,
        rotation: list[float] | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Set the placement (position and rotation) of a FreeCAD object.

        Args:
            object_name: Name of the object to move.
            position: Position as [x, y, z]. Keeps current if None.
            rotation: Rotation as [yaw, pitch, roll] in degrees. Keeps current if None.
            doc_name: Document containing the object. Uses active document if None.

        Returns:
            Dictionary with new placement:
                - position: New position [x, y, z]
                - rotation: New rotation angles
        """
        bridge = await get_bridge()

        pos_str = (
            f"FreeCAD.Vector({position[0]}, {position[1]}, {position[2]})"
            if position
            else "obj.Placement.Base"
        )
        rot_str = (
            f"FreeCAD.Rotation({rotation[0]}, {rotation[1]}, {rotation[2]})"
            if rotation
            else "obj.Placement.Rotation"
        )

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

obj = doc.getObject({object_name!r})
if obj is None:
    raise ValueError(f"Object not found: {object_name!r}")

pos = {pos_str}
rot = {rot_str}

obj.Placement = FreeCAD.Placement(pos, rot)
doc.recompute()

_result_ = {{
    "position": [obj.Placement.Base.x, obj.Placement.Base.y, obj.Placement.Base.z],
    "rotation": list(obj.Placement.Rotation.toEuler()),
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Set placement failed")

    @mcp.tool()
    async def scale_object(
        object_name: str,
        scale: float | list[float],
        result_name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Scale an object uniformly or non-uniformly.

        Creates a new scaled copy using Part.Scale.

        Args:
            object_name: Name of the object to scale.
            scale: Scale factor. Can be:
                - A single float for uniform scaling
                - A list [sx, sy, sz] for non-uniform scaling
            result_name: Name for the result object. Auto-generated if None.
            doc_name: Document containing the object. Uses active document if None.

        Returns:
            Dictionary with result object information:
                - name: Result object name
                - label: Result object label
                - type_id: Result object type
        """
        bridge = await get_bridge()

        if isinstance(scale, int | float):
            scale_vec = f"FreeCAD.Vector({scale}, {scale}, {scale})"
        else:
            scale_vec = f"FreeCAD.Vector({scale[0]}, {scale[1]}, {scale[2]})"

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

obj = doc.getObject({object_name!r})
if obj is None:
    raise ValueError(f"Object not found: {object_name!r}")

if not hasattr(obj, "Shape"):
    raise ValueError("Object has no shape to scale")

import Part

scale_vec = {scale_vec}
center = obj.Shape.BoundBox.Center

# Create scaled shape
mat = FreeCAD.Matrix()
mat.scale(scale_vec)
scaled_shape = obj.Shape.transformGeometry(mat)

# Create result object
result_name = {result_name!r} or f"{{obj.Name}}_scaled"
result = doc.addObject("Part::Feature", result_name)
result.Shape = scaled_shape

doc.recompute()

_result_ = {{
    "name": result.Name,
    "label": result.Label,
    "type_id": result.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Scale operation failed")

    @mcp.tool()
    async def rotate_object(
        object_name: str,
        axis: list[float],
        angle: float,
        center: list[float] | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Rotate an object around an axis.

        Modifies the object's placement in-place.

        Args:
            object_name: Name of the object to rotate.
            axis: Rotation axis as [x, y, z] vector.
            angle: Rotation angle in degrees.
            center: Center point for rotation [x, y, z].
                    Uses object center if None.
            doc_name: Document containing the object. Uses active document if None.

        Returns:
            Dictionary with new placement:
                - position: New position [x, y, z]
                - rotation: New rotation angles
        """
        bridge = await get_bridge()

        center_str = (
            f"FreeCAD.Vector({center[0]}, {center[1]}, {center[2]})"
            if center
            else "obj.Shape.BoundBox.Center if hasattr(obj, 'Shape') else FreeCAD.Vector(0,0,0)"
        )

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

obj = doc.getObject({object_name!r})
if obj is None:
    raise ValueError(f"Object not found: {object_name!r}")

axis = FreeCAD.Vector({axis[0]}, {axis[1]}, {axis[2]})
center = {center_str}

# Create rotation
rot = FreeCAD.Rotation(axis, {angle})

# Apply rotation around center
old_placement = obj.Placement
new_rot = rot.multiply(old_placement.Rotation)

# Adjust position for rotation around center
pos_vec = old_placement.Base - center
rotated_pos = rot.multVec(pos_vec) + center

obj.Placement = FreeCAD.Placement(rotated_pos, new_rot)
doc.recompute()

_result_ = {{
    "position": [obj.Placement.Base.x, obj.Placement.Base.y, obj.Placement.Base.z],
    "rotation": list(obj.Placement.Rotation.toEuler()),
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Rotate operation failed")

    @mcp.tool()
    async def copy_object(
        object_name: str,
        new_name: str | None = None,
        offset: list[float] | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a copy of an object.

        Args:
            object_name: Name of the object to copy.
            new_name: Name for the copy. Auto-generated if None.
            offset: Position offset [x, y, z] for the copy. [0,0,0] if None.
            doc_name: Document containing the object. Uses active document if None.

        Returns:
            Dictionary with copy object information:
                - name: Copy object name
                - label: Copy object label
                - type_id: Copy object type
        """
        bridge = await get_bridge()

        offset_str = (
            f"[{offset[0]}, {offset[1]}, {offset[2]}]" if offset else "[0, 0, 0]"
        )

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

obj = doc.getObject({object_name!r})
if obj is None:
    raise ValueError(f"Object not found: {object_name!r}")

# Create copy
new_name = {new_name!r} or f"{{obj.Name}}_copy"

if hasattr(obj, "Shape"):
    copy_obj = doc.addObject("Part::Feature", new_name)
    copy_obj.Shape = obj.Shape.copy()
else:
    # For non-shape objects, create simple copy
    copy_obj = doc.copyObject(obj, False)
    copy_obj.Label = new_name

# Apply offset
offset = {offset_str}
copy_obj.Placement.Base = FreeCAD.Vector(
    obj.Placement.Base.x + offset[0],
    obj.Placement.Base.y + offset[1],
    obj.Placement.Base.z + offset[2]
)

doc.recompute()

_result_ = {{
    "name": copy_obj.Name,
    "label": copy_obj.Label,
    "type_id": copy_obj.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Copy operation failed")

    @mcp.tool()
    async def mirror_object(
        object_name: str,
        plane: str = "XY",
        result_name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Mirror an object across a plane.

        Creates a new mirrored copy of the object.

        Args:
            object_name: Name of the object to mirror.
            plane: Mirror plane. Options: "XY", "XZ", "YZ".
            result_name: Name for the result object. Auto-generated if None.
            doc_name: Document containing the object. Uses active document if None.

        Returns:
            Dictionary with result object information:
                - name: Result object name
                - label: Result object label
                - type_id: Result object type
        """
        bridge = await get_bridge()

        plane_map = {
            "XY": "(0, 0, 1)",
            "XZ": "(0, 1, 0)",
            "YZ": "(1, 0, 0)",
        }

        if plane not in plane_map:
            raise ValueError(f"Invalid plane: {plane}. Use: XY, XZ, YZ")

        normal = plane_map[plane]

        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

obj = doc.getObject({object_name!r})
if obj is None:
    raise ValueError(f"Object not found: {object_name!r}")

if not hasattr(obj, "Shape"):
    raise ValueError("Object has no shape to mirror")

# Create mirror matrix
import Part
normal = FreeCAD.Vector{normal}
center = obj.Shape.BoundBox.Center

# Mirror the shape
mirrored = obj.Shape.mirror(center, normal)

# Create result object
result_name = {result_name!r} or f"{{obj.Name}}_mirror"
result = doc.addObject("Part::Feature", result_name)
result.Shape = mirrored

doc.recompute()

_result_ = {{
    "name": result.Name,
    "label": result.Label,
    "type_id": result.TypeId,
}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Mirror operation failed")

    @mcp.tool()
    async def get_selection(doc_name: str | None = None) -> list[dict[str, Any]]:
        """Get the current selection in FreeCAD.

        Requires GUI mode.

        Args:
            doc_name: Document to check selection in. Uses active document if None.

        Returns:
            List of selected objects with:
                - name: Object name
                - label: Object label
                - type_id: Object type
                - sub_elements: List of selected sub-elements (e.g., ["Face1", "Edge2"])
        """
        bridge = await get_bridge()

        code = f"""
if not FreeCAD.GuiUp:
    _result_ = []
else:
    sel = FreeCADGui.Selection.getSelectionEx({doc_name!r})
    _result_ = []
    for s in sel:
        _result_.append({{
            "name": s.Object.Name,
            "label": s.Object.Label,
            "type_id": s.Object.TypeId,
            "sub_elements": list(s.SubElementNames) if s.SubElementNames else [],
        }})
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        return []

    @mcp.tool()
    async def set_selection(
        object_names: list[str],
        clear_existing: bool = True,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Set the selection in FreeCAD.

        Requires GUI mode.

        Args:
            object_names: List of object names to select.
            clear_existing: Whether to clear existing selection first. Defaults to True.
            doc_name: Document containing the objects. Uses active document if None.

        Returns:
            Dictionary with result:
                - success: Whether operation was successful
                - selected_count: Number of objects selected
        """
        bridge = await get_bridge()

        code = f"""
if not FreeCAD.GuiUp:
    _result_ = {{"success": False, "error": "GUI not available"}}
else:
    doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
    if doc is None:
        raise ValueError("No document found")

    if {clear_existing}:
        FreeCADGui.Selection.clearSelection()

    count = 0
    for name in {object_names!r}:
        obj = doc.getObject(name)
        if obj:
            FreeCADGui.Selection.addSelection(obj)
            count += 1

    _result_ = {{"success": True, "selected_count": count}}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Set selection failed")

    @mcp.tool()
    async def clear_selection() -> dict[str, Any]:
        """Clear the current selection in FreeCAD.

        Requires GUI mode.

        Returns:
            Dictionary with result:
                - success: Whether operation was successful
        """
        bridge = await get_bridge()

        code = """
if not FreeCAD.GuiUp:
    _result_ = {"success": False, "error": "GUI not available"}
else:
    FreeCADGui.Selection.clearSelection()
    _result_ = {"success": True}
"""
        result = await bridge.execute_python(code)
        if result.success:
            return result.result
        raise ValueError(result.error_traceback or "Clear selection failed")
