"""Integration tests for the CutObjectForMagnets macro.

These tests verify the SmartCutter class functionality including:
- Cutting solid objects with boolean hole operations
- Cutting hollow objects with boolean hole operations
- Boolean hole creation method (primary method for CI compatibility)
- Edge cases and error handling

Test Organization:
- TestCutSolidObject: Tests cutting solid objects with boolean holes
- TestCutHollowObject: Tests cutting hollow objects with boolean holes
- TestBooleanHoleFallback: Tests for the boolean hole creation method
- TestEdgeCases: Edge case tests (single hole, many holes)

Note: These tests require a running FreeCAD MCP bridge.
      Start it with: just freecad::run-gui or just freecad::run-headless

Note: PartDesign::Hole has a CADKernelError bug in some FreeCAD headless
      environments (especially AppImage on Linux CI) where it fails with
      "Cannot make face from profile". These tests use boolean holes instead,
      which work reliably in both GUI and headless mode.

To run these tests:
    pytest tests/integration/test_cut_object_for_magnets.py -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    import xmlrpc.client

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# Note: xmlrpc_proxy fixture is defined in conftest.py


def execute_code(proxy: xmlrpc.client.ServerProxy, code: str) -> dict[str, Any]:
    """Execute Python code via the MCP bridge and return the result."""
    result: dict[str, Any] = proxy.execute(code)  # type: ignore[assignment]
    assert result.get("success"), f"Execution failed: {result.get('error_traceback')}"
    return result


# The SmartCutter class code embedded for testing
# This avoids issues with importing the macro file directly
SMART_CUTTER_CODE = '''
import FreeCAD as App
import Part


class HolePlacementError(Exception):
    """Raised when hole placement fails."""
    pass


class SmartCutter:
    """Handles cutting objects and placing magnet holes with collision detection."""

    def __init__(self, obj, params: dict):
        """Initialize the cutter."""
        self.obj = obj
        self.params = params
        self.shape = obj.Shape

    def get_cut_plane_normal_and_point(self):
        """Get plane normal vector and point based on selected plane."""
        plane_type = self.params.get("plane_type", "Preset Plane")

        plane = self.params["plane"]
        offset = self.params["offset"]

        if plane == "XY":
            normal = App.Vector(0, 0, 1)
            point = App.Vector(0, 0, offset)
        elif plane == "XZ":
            normal = App.Vector(0, 1, 0)
            point = App.Vector(0, offset, 0)
        elif plane == "YZ":
            normal = App.Vector(1, 0, 0)
            point = App.Vector(offset, 0, 0)
        else:
            normal = App.Vector(0, 0, 1)
            point = App.Vector(0, 0, offset)

        return normal, point

    def cut_object(self):
        """Cut the object along the specified plane."""
        normal, point = self.get_cut_plane_normal_and_point()

        bbox = self.shape.BoundBox
        size = max(bbox.XLength, bbox.YLength, bbox.ZLength) * 3

        half = size / 2
        box = Part.makeBox(size, size, size, App.Vector(-half, -half, 0))

        z_axis = App.Vector(0, 0, 1)
        rotation = App.Rotation(z_axis, normal)

        box = box.transformed(App.Matrix(rotation.toMatrix()))
        box.translate(point)

        try:
            bottom_part = self.shape.cut(box)
            top_part = self.shape.common(box)
            return bottom_part, top_part
        except Exception as e:
            raise HolePlacementError(f"Failed to cut object: {e!s}") from e

    def get_cut_face_center(self, part, normal):
        """Find the center of the cut face on a part."""
        _, cut_point = self.get_cut_plane_normal_and_point()

        best_face = None
        best_dist = float("inf")

        for face in part.Faces:
            face_normal = face.normalAt(0, 0)
            dot = abs(face_normal.dot(normal))
            if dot > 0.99:
                face_center = face.CenterOfMass
                dist_along_normal = abs((face_center - cut_point).dot(normal))
                if dist_along_normal < best_dist:
                    best_dist = dist_along_normal
                    best_face = face

        if best_face is not None:
            return best_face.CenterOfMass
        return None

    def is_hole_safe(self, center, direction, part, clearance=None):
        """Check if a hole at this position would penetrate the outer surface."""
        diameter = self.params["diameter"]
        depth = self.params["depth"]
        if clearance is None:
            clearance = self.params["clearance_min"]

        dir_normalized = App.Vector(direction).normalize()
        radius_check = (diameter / 2) + clearance
        start_offset = 0.5

        start_pos = center + (dir_normalized * start_offset)
        test_length = depth - start_offset

        if test_length <= 0:
            return True

        test_cylinder = Part.makeCylinder(
            radius_check, test_length, start_pos, dir_normalized
        )

        try:
            intersection = part.common(test_cylinder)
            cylinder_vol = test_cylinder.Volume
            intersection_vol = intersection.Volume

            if intersection_vol < cylinder_vol * 0.95:
                return False

            return True
        except Exception:
            return False

    def generate_hole_positions(self, cut_face_center, cut_face):
        """Generate hole positions evenly distributed along the perimeter."""
        hole_count = self.params["hole_count"]
        clearance = self.params["clearance_preferred"]
        diameter = self.params["diameter"]

        wires = cut_face.Wires
        if not wires:
            return [], None, 0, []

        outer_wire = max(wires, key=lambda w: w.Length)
        perimeter_length = outer_wire.Length

        inset = clearance + (diameter / 2)

        normal, _ = self.get_cut_plane_normal_and_point()
        normal = App.Vector(normal).normalize()

        if hole_count < 1:
            return [], outer_wire, perimeter_length, []

        spacing = perimeter_length / hole_count

        positions = []
        original_params = []

        for i in range(hole_count):
            param = (i * spacing) + (spacing / 2)
            if param >= perimeter_length:
                param = param - perimeter_length

            edge_point = self._get_point_at_length(outer_wire, param)
            if edge_point is None:
                continue

            inset_point = self._get_inset_point(edge_point, cut_face, normal, inset)

            if inset_point:
                positions.append(inset_point)
                original_params.append(param)

        return positions, outer_wire, perimeter_length, original_params

    def _get_point_at_length(self, wire, length):
        """Get a point on the wire at a specific length along it."""
        cumulative_length = 0.0

        for edge in wire.Edges:
            edge_length = edge.Length

            if cumulative_length + edge_length >= length:
                remaining = length - cumulative_length
                param = remaining / edge_length if edge_length > 0 else 0

                first_param = edge.FirstParameter
                last_param = edge.LastParameter
                edge_param = first_param + param * (last_param - first_param)

                try:
                    point = edge.valueAt(edge_param)
                    return App.Vector(point)
                except Exception:
                    return None

            cumulative_length += edge_length

        return None

    def _get_inset_point(self, edge_point, cut_face, normal, inset):
        """Get a point that is inset from the edge toward the face interior."""
        face_center = cut_face.CenterOfMass

        to_center = face_center - edge_point
        to_center = to_center - normal * (to_center.dot(normal))

        if to_center.Length < 0.001:
            return None

        to_center_normalized = App.Vector(to_center).normalize()
        inset_point = edge_point + (to_center_normalized * inset)

        try:
            dist_info = cut_face.distToShape(Part.Vertex(inset_point))
            dist = dist_info[0]

            if dist < 0.5:
                closest_on_face = dist_info[1][0][0]
                return App.Vector(closest_on_face)
            else:
                dist_info = cut_face.distToShape(Part.Vertex(inset_point))
                return App.Vector(dist_info[1][0][0])
        except Exception:
            return None

    def _check_hole_overlap(self, positions, new_pos):
        """Check if a new hole position would overlap with existing holes."""
        diameter = self.params["diameter"]
        min_distance = diameter * 2

        for existing_pos in positions:
            dist = (new_pos - existing_pos).Length
            if dist < min_distance:
                return False

        return True

    def execute(self, progress_callback=None, use_boolean=True):
        """Execute the complete cutting and hole placement operation.

        Args:
            progress_callback: Optional callback for progress updates.
            use_boolean: If True, use boolean holes (CI-compatible).
                         If False, use PartDesign::Hole (may fail in some headless envs).
        """
        bottom_shape, top_shape = self.cut_object()

        normal, _ = self.get_cut_plane_normal_and_point()

        bottom_face_center = self.get_cut_face_center(bottom_shape, -normal)
        top_face_center = self.get_cut_face_center(top_shape, normal)

        if not bottom_face_center or not top_face_center:
            raise HolePlacementError("Could not find cut faces")

        bottom_cut_face = None
        for face in bottom_shape.Faces:
            if face.CenterOfMass.distanceToPoint(bottom_face_center) < 0.1:
                bottom_cut_face = face
                break

        if not bottom_cut_face:
            raise HolePlacementError("Could not find bottom cut face")

        top_cut_face = None
        for face in top_shape.Faces:
            if face.CenterOfMass.distanceToPoint(top_face_center) < 0.1:
                top_cut_face = face
                break

        if not top_cut_face:
            raise HolePlacementError("Could not find top cut face")

        initial_positions, outer_wire, perimeter_length, original_params = (
            self.generate_hole_positions(bottom_face_center, bottom_cut_face)
        )

        if not initial_positions:
            raise HolePlacementError("No valid hole positions found")

        clearance_preferred = self.params["clearance_preferred"]
        validated_positions = []

        for idx, pos in enumerate(initial_positions):
            bottom_safe = self.is_hole_safe(pos, -normal, bottom_shape, clearance_preferred)
            top_safe = self.is_hole_safe(pos, normal, top_shape, clearance_preferred)

            if bottom_safe and top_safe:
                if self._check_hole_overlap(validated_positions, pos):
                    validated_positions.append(pos)

        if not validated_positions:
            raise HolePlacementError("No valid hole positions found after validation")

        if use_boolean:
            # Use boolean holes (works reliably in headless mode)
            bottom_with_holes = self._create_holes_boolean(bottom_shape, -normal, validated_positions)
            top_with_holes = self._create_holes_boolean(top_shape, normal, validated_positions)

            # Create Part::Feature objects for results
            doc = App.ActiveDocument
            bottom_obj = doc.addObject("Part::Feature", f"{self.obj.Label}_Bottom")
            bottom_obj.Shape = bottom_with_holes
            top_obj = doc.addObject("Part::Feature", f"{self.obj.Label}_Top")
            top_obj.Shape = top_with_holes
            doc.recompute()

            return bottom_obj, top_obj
        else:
            # Use PartDesign::Hole (may fail with CADKernelError in some headless envs)
            # Create PartDesign::Body objects from shapes
            bottom_body = self._create_body_from_shape(
                bottom_shape, f"{self.obj.Label}_Bottom"
            )
            top_body = self._create_body_from_shape(top_shape, f"{self.obj.Label}_Top")

            # Find cut face names on the new bodies
            bottom_face_name = self._find_cut_face_name(bottom_body, -normal)
            top_face_name = self._find_cut_face_name(top_body, normal)

            # Create hole sketches with points at validated positions
            bottom_sketch = self._create_hole_sketch(
                bottom_body, bottom_face_name, validated_positions
            )

            top_sketch = self._create_hole_sketch(
                top_body, top_face_name, validated_positions
            )

            # Create PartDesign::Hole features
            self._create_hole_feature(
                bottom_body, bottom_sketch, self.params["diameter"], self.params["depth"]
            )

            self._create_hole_feature(
                top_body, top_sketch, self.params["diameter"], self.params["depth"]
            )

            return bottom_body, top_body

    def _create_body_from_shape(self, shape, name):
        """Create a PartDesign::Body containing the given shape."""
        doc = App.ActiveDocument

        base_feature_name = f"{name}_Base"
        feature = doc.addObject("Part::Feature", base_feature_name)
        feature.Shape = shape

        body = doc.addObject("PartDesign::Body", name)
        body.BaseFeature = feature

        if hasattr(feature, "ViewObject") and feature.ViewObject:
            feature.ViewObject.Visibility = False

        doc.recompute()
        return body

    def _find_cut_face_name(self, body, normal):
        """Find the name of the cut face on a PartDesign::Body's Tip feature."""
        tip_feature = body.Tip
        if tip_feature is None:
            raise HolePlacementError(f"Body {body.Label} has no Tip feature")

        shape = tip_feature.Shape
        target_normal = App.Vector(normal).normalize()

        best_face_idx = None
        best_dot = -1

        for i, face in enumerate(shape.Faces):
            try:
                face_normal = face.normalAt(0.5, 0.5)
                dot = face_normal.dot(target_normal)

                if dot > best_dot:
                    best_dot = dot
                    best_face_idx = i
            except Exception:
                continue

        if best_face_idx is not None and best_dot > 0.99:
            return f"Face{best_face_idx + 1}"

        raise HolePlacementError(
            f"Could not find cut face on body {body.Label}. "
            f"Best match had dot product {best_dot:.3f}"
        )

    def _world_to_sketch_coords(self, world_pos, sketch):
        """Transform world coordinates to sketch-local 2D coordinates."""
        placement = sketch.Placement
        inv_placement = placement.inverse()
        local_pos = inv_placement.multVec(world_pos)
        return App.Vector(local_pos.x, local_pos.y, 0)

    def _create_hole_sketch(self, body, cut_face_name, positions):
        """Create a sketch with points at hole center positions."""
        sketch = body.newObject("Sketcher::SketchObject", "HoleCenters")

        tip_feature = body.Tip
        if tip_feature is None:
            raise HolePlacementError(f"Body {body.Label} has no Tip feature")

        sketch.AttachmentSupport = [(tip_feature, cut_face_name)]
        sketch.MapMode = "FlatFace"

        App.ActiveDocument.recompute()

        for pos in positions:
            local_pos = self._world_to_sketch_coords(pos, sketch)
            sketch.addGeometry(
                Part.Point(App.Vector(local_pos.x, local_pos.y, 0)),
                False,
            )

        App.ActiveDocument.recompute()
        return sketch

    def _create_hole_feature(self, body, sketch, diameter, depth):
        """Create a PartDesign::Hole feature from a sketch with point geometry."""
        hole = body.newObject("PartDesign::Hole", "MagnetHoles")
        hole.Profile = sketch
        hole.Diameter = diameter
        hole.Depth = depth
        hole.DepthType = "Dimension"
        hole.Threaded = False
        hole.HoleCutType = "None"

        App.ActiveDocument.recompute()
        return hole

    def _create_holes_boolean(self, part, direction, positions):
        """Create holes using boolean operations (alternative method).

        This is an alternative to PartDesign::Hole that uses Part boolean
        operations. Both methods work in GUI and headless mode.
        """
        diameter = self.params["diameter"]
        depth = self.params["depth"]

        dir_normalized = App.Vector(direction).normalize()

        result = part
        holes_created = 0

        for pos in positions:
            offset = 0.1
            start_pos = pos - (dir_normalized * offset)
            hole_length = depth + offset

            try:
                hole = Part.makeCylinder(
                    diameter / 2, hole_length, start_pos, dir_normalized
                )
                result = result.cut(hole)
                holes_created += 1
            except Exception:
                pass

        return result
'''


class TestCutSolidObject:
    """Tests for cutting solid objects with boolean hole operations.

    These tests work in both GUI and headless mode.
    """

    @pytest.fixture(autouse=True)
    def setup_document(self, xmlrpc_proxy: xmlrpc.client.ServerProxy) -> None:
        """Create a fresh document for each test."""
        execute_code(
            xmlrpc_proxy,
            """
import FreeCAD
if "CutMacroTestDoc" in FreeCAD.listDocuments():
    FreeCAD.closeDocument("CutMacroTestDoc")
doc = FreeCAD.newDocument("CutMacroTestDoc")
_result_ = True
""",
        )

    def test_cut_solid_box_with_boolean_holes(
        self, xmlrpc_proxy: xmlrpc.client.ServerProxy
    ) -> None:
        """Test cutting a solid box and creating boolean holes."""
        result = execute_code(
            xmlrpc_proxy,
            SMART_CUTTER_CODE
            + """
doc = App.ActiveDocument

# Create a solid box: 50x50x40mm
box = Part.makeBox(50, 50, 40)
box_obj = doc.addObject("Part::Feature", "TestBox")
box_obj.Shape = box
doc.recompute()

# Calculate original volume for comparison
original_volume = box.Volume

# Create SmartCutter with parameters
params = {
    "plane_type": "Preset Plane",
    "plane": "XY",
    "offset": 20.0,  # Cut in the middle
    "diameter": 6.0,
    "depth": 3.0,
    "hole_count": 4,
    "clearance_preferred": 2.0,
    "clearance_min": 0.5,
}

cutter = SmartCutter(box_obj, params)

# Execute the cut with boolean holes (use_boolean=True is the default)
bottom_obj, top_obj = cutter.execute()

doc.recompute()

# Calculate expected hole volume
import math
hole_volume = math.pi * (params["diameter"] / 2) ** 2 * params["depth"]

# Verify results
_result_ = {
    "success": True,
    "bottom_type": bottom_obj.TypeId,
    "top_type": top_obj.TypeId,
    "bottom_name": bottom_obj.Label,
    "top_name": top_obj.Label,
    "bottom_volume": bottom_obj.Shape.Volume,
    "top_volume": top_obj.Shape.Volume,
    "bottom_valid": bottom_obj.Shape.isValid(),
    "top_valid": top_obj.Shape.isValid(),
    "original_volume": original_volume,
    "hole_volume_each": hole_volume,
    # Combined volume should be less than original due to holes
    "total_volume": bottom_obj.Shape.Volume + top_obj.Shape.Volume,
}

# Volume should have decreased from original (holes were cut)
_result_["volume_decreased"] = _result_["total_volume"] < original_volume
""",
        )

        assert result["result"]["success"] is True
        # Boolean method produces Part::Feature objects
        assert result["result"]["bottom_type"] == "Part::Feature"
        assert result["result"]["top_type"] == "Part::Feature"
        assert "Bottom" in result["result"]["bottom_name"]
        assert "Top" in result["result"]["top_name"]
        assert result["result"]["bottom_valid"] is True
        assert result["result"]["top_valid"] is True
        # Volumes should be positive
        assert result["result"]["bottom_volume"] > 0
        assert result["result"]["top_volume"] > 0
        # Volume should have decreased due to holes
        assert result["result"]["volume_decreased"] is True


class TestCutHollowObject:
    """Tests for cutting hollow objects with boolean hole operations.

    These tests work in both GUI and headless mode.
    """

    @pytest.fixture(autouse=True)
    def setup_document(self, xmlrpc_proxy: xmlrpc.client.ServerProxy) -> None:
        """Create a fresh document for each test."""
        execute_code(
            xmlrpc_proxy,
            """
import FreeCAD
if "CutHollowTestDoc" in FreeCAD.listDocuments():
    FreeCAD.closeDocument("CutHollowTestDoc")
doc = FreeCAD.newDocument("CutHollowTestDoc")
_result_ = True
""",
        )

    def test_cut_hollow_cylinder_with_boolean_holes(
        self, xmlrpc_proxy: xmlrpc.client.ServerProxy
    ) -> None:
        """Test cutting a hollow cylinder (vase shape) with boolean holes."""
        result = execute_code(
            xmlrpc_proxy,
            SMART_CUTTER_CODE
            + """
import math

doc = App.ActiveDocument

# Create a hollow vase-shaped cylinder
# Outer cylinder: radius 20mm, height 60mm
# Inner cylinder: radius 13mm (wall thickness 7mm), height 55mm (5mm bottom)
outer_radius = 20.0
inner_radius = 13.0
height = 60.0
bottom_thickness = 5.0

# Create outer cylinder
outer = Part.makeCylinder(outer_radius, height)

# Create inner cylinder (starting above bottom)
inner = Part.makeCylinder(inner_radius, height - bottom_thickness, App.Vector(0, 0, bottom_thickness))

# Cut inner from outer to make hollow vase
vase_shape = outer.cut(inner)

vase_obj = doc.addObject("Part::Feature", "TestVase")
vase_obj.Shape = vase_shape
doc.recompute()

# Calculate original volume
original_volume = vase_shape.Volume

# Create SmartCutter with parameters
params = {
    "plane_type": "Preset Plane",
    "plane": "XY",
    "offset": 30.0,  # Cut at 30mm height (middle of vase)
    "diameter": 3.0,  # Smaller holes for thin walls
    "depth": 3.0,
    "hole_count": 6,
    "clearance_preferred": 2.0,
    "clearance_min": 0.5,
}

cutter = SmartCutter(vase_obj, params)

# Execute the cut with boolean holes
bottom_obj, top_obj = cutter.execute()

doc.recompute()

# Verify results
_result_ = {
    "success": True,
    "bottom_type": bottom_obj.TypeId,
    "top_type": top_obj.TypeId,
    "bottom_valid": bottom_obj.Shape.isValid(),
    "top_valid": top_obj.Shape.isValid(),
    "bottom_volume": bottom_obj.Shape.Volume,
    "top_volume": top_obj.Shape.Volume,
    "original_volume": original_volume,
    "total_volume": bottom_obj.Shape.Volume + top_obj.Shape.Volume,
}

# Volume should have decreased from original (holes were cut)
_result_["volume_decreased"] = _result_["total_volume"] < original_volume
""",
        )

        assert result["result"]["success"] is True
        # Boolean method produces Part::Feature objects
        assert result["result"]["bottom_type"] == "Part::Feature"
        assert result["result"]["top_type"] == "Part::Feature"
        assert result["result"]["bottom_valid"] is True
        assert result["result"]["top_valid"] is True
        # Volumes should be positive
        assert result["result"]["bottom_volume"] > 0
        assert result["result"]["top_volume"] > 0
        # Volume should have decreased due to holes
        assert result["result"]["volume_decreased"] is True


class TestBooleanHoleFallback:
    """Tests for the fallback boolean hole creation method."""

    @pytest.fixture(autouse=True)
    def setup_document(self, xmlrpc_proxy: xmlrpc.client.ServerProxy) -> None:
        """Create a fresh document for each test."""
        execute_code(
            xmlrpc_proxy,
            """
import FreeCAD
if "BooleanHoleTestDoc" in FreeCAD.listDocuments():
    FreeCAD.closeDocument("BooleanHoleTestDoc")
doc = FreeCAD.newDocument("BooleanHoleTestDoc")
_result_ = True
""",
        )

    def test_boolean_hole_creation_fallback(
        self, xmlrpc_proxy: xmlrpc.client.ServerProxy
    ) -> None:
        """Test the _create_holes_boolean fallback method directly."""
        result = execute_code(
            xmlrpc_proxy,
            SMART_CUTTER_CODE
            + """
doc = App.ActiveDocument

# Create a solid box: 50x50x20mm
box = Part.makeBox(50, 50, 20)
box_obj = doc.addObject("Part::Feature", "TestBox")
box_obj.Shape = box
doc.recompute()

# Calculate initial volume
initial_volume = box.Volume

# Create SmartCutter with parameters
params = {
    "plane_type": "Preset Plane",
    "plane": "XY",
    "offset": 10.0,  # Cut in the middle
    "diameter": 5.0,
    "depth": 5.0,
    "hole_count": 4,
    "clearance_preferred": 2.0,
    "clearance_min": 0.5,
}

cutter = SmartCutter(box_obj, params)

# First cut the object to get the two halves
bottom_shape, top_shape = cutter.cut_object()

# Get the cut face center and face for hole position generation
normal, _ = cutter.get_cut_plane_normal_and_point()
bottom_face_center = cutter.get_cut_face_center(bottom_shape, -normal)

# Find the actual bottom cut face
bottom_cut_face = None
for face in bottom_shape.Faces:
    if face.CenterOfMass.distanceToPoint(bottom_face_center) < 0.1:
        bottom_cut_face = face
        break

# Generate hole positions
positions, _, _, _ = cutter.generate_hole_positions(bottom_face_center, bottom_cut_face)

# Apply boolean hole method to bottom shape
# Note: holes go in -normal direction (into the bottom part)
bottom_with_holes = cutter._create_holes_boolean(bottom_shape, -normal, positions)

# Calculate expected volume reduction per hole
import math
hole_volume = math.pi * (params["diameter"] / 2) ** 2 * params["depth"]
expected_reduction = hole_volume * len(positions)

# Create Part::Feature objects for the results
bottom_result = doc.addObject("Part::Feature", "BottomWithHoles")
bottom_result.Shape = bottom_with_holes
doc.recompute()

# Verify results
_result_ = {
    "success": True,
    "initial_volume": initial_volume,
    "bottom_half_volume_before": bottom_shape.Volume,
    "bottom_with_holes_volume": bottom_with_holes.Volume,
    "positions_count": len(positions),
    "hole_volume_each": hole_volume,
    "expected_volume_reduction": expected_reduction,
    "actual_volume_reduction": bottom_shape.Volume - bottom_with_holes.Volume,
    "bottom_valid": bottom_with_holes.isValid(),
    "result_type": bottom_result.TypeId,
}

# Volume should have decreased by approximately the hole volumes
volume_diff = abs(_result_["actual_volume_reduction"] - expected_reduction)
_result_["volume_reduction_accurate"] = volume_diff < 1.0  # Within 1 mm^3 tolerance
""",
        )

        assert result["result"]["success"] is True
        assert result["result"]["bottom_valid"] is True
        assert (
            result["result"]["result_type"] == "Part::Feature"
        )  # Boolean result is Part::Feature, not PartDesign
        assert result["result"]["positions_count"] >= 1
        # Volume should have decreased
        assert (
            result["result"]["bottom_with_holes_volume"]
            < result["result"]["bottom_half_volume_before"]
        )
        # Volume reduction should be close to expected
        assert result["result"]["volume_reduction_accurate"] is True

    def test_boolean_method_consistency(
        self, xmlrpc_proxy: xmlrpc.client.ServerProxy
    ) -> None:
        """Verify boolean hole method produces consistent results on identical objects."""
        result = execute_code(
            xmlrpc_proxy,
            SMART_CUTTER_CODE
            + """
doc = App.ActiveDocument

# Create two identical solid boxes
box1 = Part.makeBox(50, 50, 20)
box1_obj = doc.addObject("Part::Feature", "Box1")
box1_obj.Shape = box1

box2 = Part.makeBox(50, 50, 20)
box2_obj = doc.addObject("Part::Feature", "Box2")
box2_obj.Shape = box2

doc.recompute()

# Same parameters for both
params = {
    "plane_type": "Preset Plane",
    "plane": "XY",
    "offset": 10.0,
    "diameter": 5.0,
    "depth": 5.0,
    "hole_count": 4,
    "clearance_preferred": 3.0,
    "clearance_min": 1.0,
}

# Run 1: Boolean method on box1
cutter1 = SmartCutter(box1_obj, params)
result1_bottom, result1_top = cutter1.execute()  # use_boolean=True is default

# Run 2: Boolean method on box2 (identical operation)
cutter2 = SmartCutter(box2_obj, params)
result2_bottom, result2_top = cutter2.execute()

doc.recompute()

# Compare results - should be identical for same inputs
vol1_bottom = result1_bottom.Shape.Volume
vol1_top = result1_top.Shape.Volume
vol2_bottom = result2_bottom.Shape.Volume
vol2_top = result2_top.Shape.Volume

_result_ = {
    "success": True,
    "run1_bottom_volume": vol1_bottom,
    "run1_top_volume": vol1_top,
    "run2_bottom_volume": vol2_bottom,
    "run2_top_volume": vol2_top,
    "run1_bottom_type": result1_bottom.TypeId,
    "run2_bottom_type": result2_bottom.TypeId,
    # Volumes should be identical for same inputs
    "volumes_match": abs(vol1_bottom - vol2_bottom) < 0.01 and abs(vol1_top - vol2_top) < 0.01,
    "run1_bottom_valid": result1_bottom.Shape.isValid(),
    "run1_top_valid": result1_top.Shape.isValid(),
    "run2_bottom_valid": result2_bottom.Shape.isValid(),
    "run2_top_valid": result2_top.Shape.isValid(),
}
""",
        )

        assert result["result"]["success"] is True
        # Both runs should produce valid shapes
        assert result["result"]["run1_bottom_valid"] is True
        assert result["result"]["run1_top_valid"] is True
        assert result["result"]["run2_bottom_valid"] is True
        assert result["result"]["run2_top_valid"] is True
        # Boolean method produces Part::Feature objects
        assert result["result"]["run1_bottom_type"] == "Part::Feature"
        assert result["result"]["run2_bottom_type"] == "Part::Feature"
        # Volumes should be identical for same inputs
        assert result["result"]["volumes_match"] is True


class TestEdgeCases:
    """Tests for edge cases and error handling.

    These tests work in both GUI and headless mode.
    """

    @pytest.fixture(autouse=True)
    def setup_document(self, xmlrpc_proxy: xmlrpc.client.ServerProxy) -> None:
        """Create a fresh document for each test."""
        execute_code(
            xmlrpc_proxy,
            """
import FreeCAD
if "EdgeCaseTestDoc" in FreeCAD.listDocuments():
    FreeCAD.closeDocument("EdgeCaseTestDoc")
doc = FreeCAD.newDocument("EdgeCaseTestDoc")
_result_ = True
""",
        )

    def test_small_hole_count(self, xmlrpc_proxy: xmlrpc.client.ServerProxy) -> None:
        """Test with a small number of holes on a larger box for reliable placement."""
        result = execute_code(
            xmlrpc_proxy,
            SMART_CUTTER_CODE
            + """
import math

doc = App.ActiveDocument

# Use a larger box for better hole placement with small hole counts
box = Part.makeBox(80, 80, 40)
box_obj = doc.addObject("Part::Feature", "TestBox")
box_obj.Shape = box
doc.recompute()

original_volume = box.Volume

params = {
    "plane_type": "Preset Plane",
    "plane": "XY",
    "offset": 20.0,
    "diameter": 4.0,  # Smaller holes
    "depth": 3.0,
    "hole_count": 4,  # 4 holes on 80mm box = good spacing
    "clearance_preferred": 3.0,  # Increased clearance
    "clearance_min": 1.0,
}

cutter = SmartCutter(box_obj, params)
bottom_obj, top_obj = cutter.execute()

doc.recompute()

# Calculate expected hole volume for verification
hole_volume = math.pi * (params["diameter"] / 2) ** 2 * params["depth"]

_result_ = {
    "success": True,
    "bottom_valid": bottom_obj.Shape.isValid(),
    "top_valid": top_obj.Shape.isValid(),
    "bottom_volume": bottom_obj.Shape.Volume,
    "top_volume": top_obj.Shape.Volume,
    "original_volume": original_volume,
    "total_volume": bottom_obj.Shape.Volume + top_obj.Shape.Volume,
    "hole_volume_each": hole_volume,
}

# Volume should have decreased from original (holes were cut)
_result_["volume_decreased"] = _result_["total_volume"] < original_volume
""",
        )

        assert result["result"]["success"] is True
        assert result["result"]["bottom_valid"] is True
        assert result["result"]["top_valid"] is True
        # Volume should have decreased due to holes
        assert result["result"]["volume_decreased"] is True

    def test_many_holes(self, xmlrpc_proxy: xmlrpc.client.ServerProxy) -> None:
        """Test with many holes requested (some may be skipped due to overlap)."""
        result = execute_code(
            xmlrpc_proxy,
            SMART_CUTTER_CODE
            + """
import math

doc = App.ActiveDocument

# Create a larger box to fit more holes
box = Part.makeBox(100, 100, 40)
box_obj = doc.addObject("Part::Feature", "TestBox")
box_obj.Shape = box
doc.recompute()

original_volume = box.Volume

params = {
    "plane_type": "Preset Plane",
    "plane": "XY",
    "offset": 20.0,
    "diameter": 4.0,
    "depth": 3.0,
    "hole_count": 20,  # Many holes
    "clearance_preferred": 2.0,
    "clearance_min": 0.5,
}

cutter = SmartCutter(box_obj, params)
bottom_obj, top_obj = cutter.execute()

doc.recompute()

# Calculate expected hole volume for verification
hole_volume = math.pi * (params["diameter"] / 2) ** 2 * params["depth"]

_result_ = {
    "success": True,
    "bottom_valid": bottom_obj.Shape.isValid(),
    "top_valid": top_obj.Shape.isValid(),
    "bottom_volume": bottom_obj.Shape.Volume,
    "top_volume": top_obj.Shape.Volume,
    "original_volume": original_volume,
    "total_volume": bottom_obj.Shape.Volume + top_obj.Shape.Volume,
    "hole_volume_each": hole_volume,
}

# Volume should have decreased from original (holes were cut)
_result_["volume_decreased"] = _result_["total_volume"] < original_volume
""",
        )

        assert result["result"]["success"] is True
        assert result["result"]["bottom_valid"] is True
        assert result["result"]["top_valid"] is True
        # Volume should have decreased due to holes
        assert result["result"]["volume_decreased"] is True
