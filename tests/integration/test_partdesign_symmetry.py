"""Live FreeCAD compatibility tests for symmetric Part Design operations."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from freecad_mcp.tools.partdesign import register_partdesign_tools
from tests.integration.auth_support import integration_credentials

pytestmark = pytest.mark.integration


def _register_tools(
    bridge: XmlRpcBridge,
) -> dict[str, Callable[..., Awaitable[dict[str, Any]]]]:
    """Register Part Design tools against a live XML-RPC bridge."""
    mcp = MagicMock()
    registered_tools: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}

    def tool_decorator() -> Callable[
        [Callable[..., Awaitable[dict[str, Any]]]],
        Callable[..., Awaitable[dict[str, Any]]],
    ]:
        def wrapper(
            func: Callable[..., Awaitable[dict[str, Any]]],
        ) -> Callable[..., Awaitable[dict[str, Any]]]:
            registered_tools[func.__name__] = func
            return func

        return wrapper

    mcp.tool = tool_decorator

    async def get_bridge() -> XmlRpcBridge:
        return bridge

    register_partdesign_tools(mcp, get_bridge)
    return registered_tools


def _setup_code(doc_name: str, include_base_solid: bool) -> str:
    """Create a target body whose origin object names require role lookup."""
    return f"""
import FreeCAD
import Part

doc_name = {doc_name!r}
if doc_name in FreeCAD.listDocuments():
    FreeCAD.closeDocument(doc_name)
doc = FreeCAD.newDocument(doc_name)
# Force the target body's origin objects to receive numeric name suffixes.
doc.addObject("PartDesign::Body", "AxisNameOwner")
body = doc.addObject("PartDesign::Body", "Body")

if {include_base_solid!r}:
    base = body.newObject("PartDesign::Feature", "BaseFeature")
    base.Shape = Part.makeCylinder(
        12,
        20,
        FreeCAD.Vector(-10, 0, 0),
        FreeCAD.Vector(1, 0, 0),
    )

sketch = body.newObject("Sketcher::SketchObject", "Sketch")
points = [
    FreeCAD.Vector(-5, 5, 0),
    FreeCAD.Vector(5, 5, 0),
    FreeCAD.Vector(5, 8, 0),
    FreeCAD.Vector(-5, 8, 0),
]
for index, start in enumerate(points):
    sketch.addGeometry(Part.LineSegment(start, points[(index + 1) % 4]), False)
doc.recompute()
_result_ = {{"document": doc.Name, "sketch": sketch.Name}}
"""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "feature_type", "operation_argument", "include_base_solid"),
    [
        ("pad_sketch", "PartDesign::Pad", {"length": 10.0}, False),
        ("pocket_sketch", "PartDesign::Pocket", {"length": 10.0}, True),
        (
            "revolution_sketch",
            "PartDesign::Revolution",
            {"angle": 180.0},
            False,
        ),
        ("groove_sketch", "PartDesign::Groove", {"angle": 180.0}, True),
    ],
)
@pytest.mark.parametrize("symmetric", [True, False])
async def test_live_symmetric_property_selection(
    tool_name: str,
    feature_type: str,
    operation_argument: dict[str, float],
    include_base_solid: bool,
    symmetric: bool,
) -> None:
    """Invoke each production tool against the running FreeCAD release."""
    doc_name = f"McpSymmetry_{tool_name}_{uuid4().hex}"
    bridge = XmlRpcBridge(**integration_credentials())
    await bridge.connect()

    try:
        setup = await bridge.execute_python(
            _setup_code(doc_name, include_base_solid),
        )
        assert setup.success, setup.error_traceback or setup.stderr

        tools = _register_tools(bridge)
        result = await tools[tool_name](
            sketch_name="Sketch",
            doc_name=doc_name,
            symmetric=symmetric,
            **operation_argument,
        )
        assert result["type_id"] == feature_type

        # Pocket cuts into the base solid, so its Shape keeps the base
        # bounding box; measure the cut tool (AddSubShape) instead.
        shape_expression = (
            "feature.AddSubShape" if tool_name == "pocket_sketch" else "feature.Shape"
        )
        inspection = await bridge.execute_python(
            f"""
doc = FreeCAD.getDocument({doc_name!r})
feature = doc.getObject({result["name"]!r})
properties = feature.PropertiesList
if "SideType" in properties:
    property_name = "SideType"
    value = str(feature.SideType)
elif "Midplane" in properties:
    property_name = "Midplane"
    value = bool(feature.Midplane)
elif "Symmetric" in properties:
    property_name = "Symmetric"
    value = bool(feature.Symmetric)
else:
    raise AssertionError("Feature exposes no supported symmetric property")
shape = {shape_expression}
_result_ = {{
    "property_name": property_name,
    "value": value,
    "shape_valid": bool(feature.Shape and feature.Shape.isValid()),
    "z_min": float(shape.BoundBox.ZMin),
    "z_max": float(shape.BoundBox.ZMax),
}}
"""
        )
        assert inspection.success, inspection.error_traceback or inspection.stderr
        expected_value: str | bool
        if inspection.result["property_name"] == "SideType":
            expected_value = "Symmetric" if symmetric else "One side"
        else:
            expected_value = symmetric
        assert inspection.result["value"] == expected_value
        assert inspection.result["shape_valid"] is True
        if tool_name == "pad_sketch":
            expected_z_min, expected_z_max = (-5.0, 5.0) if symmetric else (0.0, 10.0)
            assert inspection.result["z_min"] == pytest.approx(expected_z_min)
            assert inspection.result["z_max"] == pytest.approx(expected_z_max)
        elif tool_name == "pocket_sketch":
            # Pocket cuts opposite the sketch normal (-Z) by default.
            expected_z_min, expected_z_max = (-5.0, 5.0) if symmetric else (-10.0, 0.0)
            assert inspection.result["z_min"] == pytest.approx(expected_z_min)
            assert inspection.result["z_max"] == pytest.approx(expected_z_max)
    finally:
        await bridge.execute_python(
            f"""
if {doc_name!r} in FreeCAD.listDocuments():
    FreeCAD.closeDocument({doc_name!r})
_result_ = True
"""
        )
        await bridge.disconnect()


@pytest.mark.asyncio
async def test_live_pocket_symmetric_through_all() -> None:
    """Symmetric ThroughAll cuts must extend to both sides of the sketch plane.

    FreeCAD 1.1+ honours ``SideType="Symmetric"`` for every termination mode,
    including ``ThroughAll`` (the prism is mirrored around the sketch plane),
    while FreeCAD 1.0.x ignores the ``Midplane`` fallback there. On the
    supported branch the cut must reach both sides of z=0.
    """
    doc_name = f"McpSymmetry_pocket_through_{uuid4().hex}"
    bridge = XmlRpcBridge(**integration_credentials())
    await bridge.connect()

    try:
        setup = await bridge.execute_python(_setup_code(doc_name, True))
        assert setup.success, setup.error_traceback or setup.stderr

        tools = _register_tools(bridge)
        result = await tools["pocket_sketch"](
            sketch_name="Sketch",
            doc_name=doc_name,
            length=10.0,
            type="ThroughAll",
            symmetric=True,
        )
        assert result["type_id"] == "PartDesign::Pocket"
        assert result["volume_removed"] > 0.0

        inspection = await bridge.execute_python(
            f"""
doc = FreeCAD.getDocument({doc_name!r})
feature = doc.getObject({result["name"]!r})
if "SideType" not in feature.PropertiesList:
    raise AssertionError("FreeCAD without SideType cannot honour this combination")
box = feature.AddSubShape.BoundBox
_result_ = {{
    "side_type": str(feature.SideType),
    "shape_valid": bool(feature.Shape.isValid()),
    "z_min": float(box.ZMin),
    "z_max": float(box.ZMax),
}}
"""
        )
        assert inspection.success, inspection.error_traceback or inspection.stderr
        assert inspection.result["side_type"] == "Symmetric"
        assert inspection.result["shape_valid"] is True
        assert inspection.result["z_min"] < 0.0 < inspection.result["z_max"]
    finally:
        await bridge.execute_python(
            f"""
if {doc_name!r} in FreeCAD.listDocuments():
    FreeCAD.closeDocument({doc_name!r})
_result_ = True
"""
        )
        await bridge.disconnect()
