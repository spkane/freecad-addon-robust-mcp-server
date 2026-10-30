"""Live ShapeString and recompute regression tests against FreeCAD."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio

from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from freecad_mcp.tools.documents import register_document_tools
from freecad_mcp.tools.draft import register_draft_tools
from freecad_mcp.tools.partdesign import register_partdesign_tools
from tests.integration.auth_support import integration_credentials

pytestmark = pytest.mark.integration


def _tools(bridge: XmlRpcBridge) -> dict[str, Callable[..., Awaitable[Any]]]:
    """Register the production tools against the live bridge."""

    class Registry:
        def __init__(self) -> None:
            self.tools: dict[str, Callable[..., Awaitable[Any]]] = {}

        def tool(self) -> Callable[..., Any]:
            def register(
                func: Callable[..., Awaitable[Any]],
            ) -> Callable[..., Awaitable[Any]]:
                self.tools[func.__name__] = func
                return func

            return register

    registry = Registry()

    async def get_bridge() -> XmlRpcBridge:
        return bridge

    register_draft_tools(registry, get_bridge)
    register_document_tools(registry, get_bridge)
    register_partdesign_tools(registry, get_bridge)
    return registry.tools


@pytest_asyncio.fixture
async def regression_document() -> AsyncIterator[tuple[XmlRpcBridge, str]]:
    """Connect a bridge and clean up a unique temporary document."""
    name = f"ShapeStringRegression_{uuid4().hex}"
    bridge = XmlRpcBridge(**integration_credentials())
    await bridge.connect()
    try:
        yield bridge, name
    finally:
        try:
            await bridge.execute_python(
                f"if {name!r} in FreeCAD.listDocuments(): "
                f"FreeCAD.closeDocument({name!r})\n_result_ = True"
            )
        finally:
            await bridge.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("rotate_body", [False, True])
@pytest.mark.parametrize(("text", "contours"), [("O", 2), ("B", 3), ("BOLT", 7)])
async def test_shapestring_conversion_preserves_name_contours_and_placement(
    rotate_body: bool,
    text: str,
    contours: int,
    regression_document: tuple[XmlRpcBridge, str],
) -> None:
    """A named letter with a counter converts on the target body's own plane."""
    bridge, name = regression_document
    setup = await bridge.execute_python(
        f"""
import FreeCAD
doc = FreeCAD.newDocument({name!r})
doc.addObject("PartDesign::Body", "FirstBody")
target = doc.addObject("PartDesign::Body", "TargetBody")
if {rotate_body!r}:
    target.Placement = FreeCAD.Placement(FreeCAD.Vector(7, -5, 2),
    FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 30))
doc.recompute()
_result_ = doc.Name
"""
    )
    assert setup.success, setup.error_traceback
    tools = _tools(bridge)
    source = await tools["draft_shapestring"](
        text=text, size=8, name="LetterO", position=[10, 15, 3], doc_name=name
    )
    assert source["name"] != source["label"]
    if rotate_body:
        rotate = await bridge.execute_python(
            f"""
source = FreeCAD.getDocument({name!r}).getObject({source["name"]!r})
source.Placement = FreeCAD.Placement(FreeCAD.Vector(10, 15, 3),
FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 20))
source.Document.recompute()
_result_ = True
"""
        )
        assert rotate.success, rotate.error_traceback
    result = await tools["draft_shapestring_to_sketch"](
        shapestring_name=source["name"], body_name="TargetBody", doc_name=name
    )
    assert result["source"] == source["name"]
    assert result["wire_count"] == contours
    check = await bridge.execute_python(
        f"""
doc = FreeCAD.getDocument({name!r})
import Part
source = doc.getObject({source["name"]!r})
sketch = doc.getObject({result["name"]!r})
a = source.Shape.BoundBox
world_shape = sketch.Shape.copy()
world_shape.Placement = doc.getObject("TargetBody").getGlobalPlacement().multiply(world_shape.Placement)
b = world_shape.BoundBox
_result_ = {{
"source_edges": len(source.Shape.Edges),
"sketch_edges": len(sketch.Shape.Edges),
"wires": len(sketch.Shape.Wires),
"closed": all(wire.isClosed() for wire in sketch.Shape.Wires),
"state": list(sketch.State),
"null": sketch.Shape.isNull(),
"support_role": sketch.AttachmentSupport[0][0].Role,
"bbox_error": max(abs(getattr(a, key) - getattr(b, key))
                  for key in ("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax")),
"length_error": abs(source.Shape.Length - world_shape.Length),
"sample_error": max(
    Part.Vertex(edge.valueAt(edge.FirstParameter + fraction *
                             (edge.LastParameter - edge.FirstParameter)))
    .distToShape(world_shape)[0]
    for edge in source.Shape.Edges for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)
),
}}
"""
    )
    assert check.success, check.error_traceback
    assert check.result["source_edges"] == check.result["sketch_edges"]
    assert check.result["wires"] == contours
    assert check.result["closed"] and not check.result["null"]
    assert not {"Invalid", "Error"} & set(check.result["state"])
    assert check.result["support_role"] == "XY_Plane"
    if not rotate_body:
        assert check.result["bbox_error"] < 1e-6
    assert check.result["length_error"] < 1e-6
    assert check.result["sample_error"] < 1e-6
    assert (await tools["recompute_document"](doc_name=name))["success"]
    by_label = await tools["draft_shapestring_to_sketch"](
        shapestring_name="LetterO", sketch_name="StandaloneText", doc_name=name
    )
    assert by_label["source"] == source["name"]
    assert by_label["wire_count"] == contours
    with pytest.raises(ValueError, match="Invalid plane"):
        await tools["draft_shapestring_to_sketch"](
            shapestring_name=source["name"],
            body_name="TargetBody",
            plane="invalid",
            sketch_name="MustRollback",
            doc_name=name,
        )
    rollback = await bridge.execute_python(
        f"_result_ = FreeCAD.getDocument({name!r}).getObject('MustRollback') is None"
    )
    assert rollback.success and rollback.result is True


@pytest.mark.asyncio
async def test_invalid_attachment_is_reported_by_recompute(
    regression_document: tuple[XmlRpcBridge, str],
) -> None:
    """Recompute reports FreeCAD object failures even if the RPC succeeds."""
    bridge, name = regression_document
    setup = await bridge.execute_python(
        f"""
doc = FreeCAD.newDocument({name!r})
body = doc.addObject("PartDesign::Body", "Body")
sketch = doc.addObject("Sketcher::SketchObject", "InvalidSketch")
body.addObject(sketch)
sketch.AttachmentSupport = [(body.Origin.OriginFeatures[0], "")]
sketch.MapMode = "FlatFace"
doc.recompute()
_result_ = list(sketch.State)
"""
    )
    assert setup.success, setup.error_traceback
    assert "Invalid" in setup.result or "Error" in setup.result
    result = await _tools(bridge)["recompute_document"](doc_name=name)
    assert result["success"] is False
    assert any(obj["name"] == "InvalidSketch" for obj in result["invalid_objects"])


@pytest.mark.asyncio
async def test_trimmed_circle_edges_keep_boundaries(
    regression_document: tuple[XmlRpcBridge, str],
) -> None:
    """Two trimmed semicircles remain a single closed circular profile."""
    bridge, name = regression_document
    setup = await bridge.execute_python(
        f"""
import math
import Part
doc = FreeCAD.newDocument({name!r})
obj = doc.addObject("Part::Feature", "TrimmedCircle")
circle = Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), 4)
obj.Shape = Part.Wire([Part.ArcOfCircle(circle, 0, math.pi).toShape(),
                   Part.ArcOfCircle(circle, math.pi, 2 * math.pi).toShape()])
doc.recompute()
_result_ = {{"edges": len(obj.Shape.Edges), "length": obj.Shape.Length}}
"""
    )
    assert setup.success, setup.error_traceback
    assert setup.result["edges"] == 2
    result = await _tools(bridge)["draft_shapestring_to_sketch"](
        shapestring_name="TrimmedCircle", doc_name=name
    )
    check = await bridge.execute_python(
        f"""
obj = FreeCAD.getDocument({name!r}).getObject({result["name"]!r})
_result_ = {{"wires": len(obj.Shape.Wires), "closed": all(w.isClosed() for w in obj.Shape.Wires),
        "edges": len(obj.Shape.Edges), "length": obj.Shape.Length}}
"""
    )
    assert check.success, check.error_traceback
    assert check.result["wires"] == 1 and check.result["closed"]
    assert check.result["edges"] == 2
    assert check.result["length"] == pytest.approx(setup.result["length"], abs=1e-6)


@pytest.mark.asyncio
async def test_converted_text_can_cut_a_partdesign_pocket(
    regression_document: tuple[XmlRpcBridge, str],
) -> None:
    """The converted text profile removes material and retains its counter."""
    bridge, name = regression_document
    setup = await bridge.execute_python(
        f"""
import FreeCAD
import Part
doc = FreeCAD.newDocument({name!r})
body = doc.addObject("PartDesign::Body", "Body")
base = body.newObject("PartDesign::Feature", "Base")
base.Shape = Part.makeBox(40, 30, 10)
doc.recompute()
_result_ = True
"""
    )
    assert setup.success, setup.error_traceback
    tools = _tools(bridge)
    source = await tools["draft_shapestring"](
        text="O", size=5, position=[5, 5, 10], doc_name=name
    )
    sketch = await tools["draft_shapestring_to_sketch"](
        shapestring_name=source["name"], body_name="Body", doc_name=name
    )
    pocket = await tools["pocket_sketch"](
        sketch_name=sketch["name"], length=2, doc_name=name
    )
    assert pocket["volume_removed"] > 0
    check = await bridge.execute_python(
        f"""
doc = FreeCAD.getDocument({name!r})
pocket = doc.getObject({pocket["name"]!r})
source = doc.getObject({source["name"]!r})
inner = min(source.Shape.Wires, key=lambda wire: wire.BoundBox.XLength * wire.BoundBox.YLength)
bounds = inner.BoundBox
counter = FreeCAD.Vector((bounds.XMin + bounds.XMax) / 2, (bounds.YMin + bounds.YMax) / 2, 9)
_result_ = {{"valid": pocket.Shape.isValid(), "null": pocket.Shape.isNull(),
         "state": list(pocket.State), "solids": len(pocket.Shape.Solids),
         "counter_inside": pocket.Shape.isInside(counter, 1e-7, True)}}
"""
    )
    assert check.success, check.error_traceback
    assert check.result["valid"] and not check.result["null"]
    assert not {"Invalid", "Error"} & set(check.result["state"])
    assert check.result["solids"] == 1
    assert check.result["counter_inside"]


@pytest.mark.asyncio
async def test_linked_shapestring_pocket_updates_after_edit(
    regression_document: tuple[XmlRpcBridge, str],
) -> None:
    """An editable source can drive a Part Design pocket through a binder."""
    bridge, name = regression_document
    setup = await bridge.execute_python(
        f"""
import FreeCAD
import Part
doc = FreeCAD.newDocument({name!r})
body = doc.addObject("PartDesign::Body", "Body")
base = body.newObject("PartDesign::Feature", "Base")
base.Shape = Part.makeBox(40, 30, 10)
doc.recompute()
_result_ = True
"""
    )
    assert setup.success, setup.error_traceback
    source = await _tools(bridge)["draft_shapestring"](
        text="O", size=5, position=[5, 5, 10], doc_name=name
    )
    result = await bridge.execute_python(
        f"""
doc = FreeCAD.getDocument({name!r})
body = doc.getObject("Body")
source = doc.getObject({source["name"]!r})
binder = body.newObject("PartDesign::SubShapeBinder", "TextBinder")
binder.Support = [(source, [""])]
doc.recompute()
pocket = body.newObject("PartDesign::Pocket", "Pocket")
pocket.Profile = binder
pocket.Length = 2
doc.recompute()
first = {{"volume": pocket.Shape.Volume, "null": pocket.Shape.isNull(), "state": list(pocket.State)}}
source.String = "OO"
doc.recompute()
_result_ = {{"before": first, "after": {{"volume": pocket.Shape.Volume,
         "null": pocket.Shape.isNull(), "state": list(pocket.State)}}}}
"""
    )
    assert result.success, result.error_traceback
    before, after = result.result["before"], result.result["after"]
    assert not before["null"] and not after["null"]
    assert not {"Invalid", "Error"} & set(before["state"])
    assert not {"Invalid", "Error"} & set(after["state"])
    assert after["volume"] < before["volume"] < 40 * 30 * 10


@pytest.mark.asyncio
async def test_conversion_rejects_loose_edges_without_changing_document(
    regression_document: tuple[XmlRpcBridge, str],
) -> None:
    """A shape with extra edges is rejected rather than silently truncated."""
    bridge, name = regression_document
    setup = await bridge.execute_python(
        f"""
import Part
doc = FreeCAD.newDocument({name!r})
obj = doc.addObject("Part::Feature", "Source")
circle = Part.Wire([Part.makeCircle(4)])
loose = Part.makeLine(FreeCAD.Vector(10, 0, 0), FreeCAD.Vector(11, 0, 0))
obj.Shape = Part.makeCompound([circle, loose])
doc.recompute()
_result_ = {{"wires": len(obj.Shape.Wires), "edges": len(obj.Shape.Edges)}}
"""
    )
    assert setup.success, setup.error_traceback
    assert setup.result == {"wires": 1, "edges": 2}
    with pytest.raises(ValueError, match="edges outside"):
        await _tools(bridge)["draft_shapestring_to_sketch"](
            shapestring_name="Source", sketch_name="MustNotExist", doc_name=name
        )
    result = await bridge.execute_python(
        f"_result_ = FreeCAD.getDocument({name!r}).getObject('MustNotExist') is None"
    )
    assert result.success and result.result is True


@pytest.mark.asyncio
@pytest.mark.parametrize("plane", ["XY_Plane", "XZ_Plane", "YZ_Plane"])
async def test_conversion_uses_requested_body_plane(
    plane: str, regression_document: tuple[XmlRpcBridge, str]
) -> None:
    """A body sketch attaches to the origin plane requested by its role."""
    bridge, name = regression_document
    setup = await bridge.execute_python(
        f"""
doc = FreeCAD.newDocument({name!r})
doc.addObject("PartDesign::Body", "FirstBody")
doc.addObject("PartDesign::Body", "TargetBody")
doc.recompute()
_result_ = True
"""
    )
    assert setup.success, setup.error_traceback
    tools = _tools(bridge)
    source = await tools["draft_shapestring"](text="O", size=5, doc_name=name)
    sketch = await tools["draft_shapestring_to_sketch"](
        shapestring_name=source["name"],
        body_name="TargetBody",
        plane=plane,
        doc_name=name,
    )
    check = await bridge.execute_python(
        f"""
doc = FreeCAD.getDocument({name!r})
sketch = doc.getObject({sketch["name"]!r})
normal = sketch.getGlobalPlacement().Rotation.multVec(FreeCAD.Vector(0, 0, 1))
_result_ = {{"role": sketch.AttachmentSupport[0][0].Role,
        "normal": [normal.x, normal.y, normal.z], "null": sketch.Shape.isNull()}}
"""
    )
    assert check.success, check.error_traceback
    assert check.result["role"] == plane
    assert not check.result["null"]
    expected = {
        "XY_Plane": [0, 0, 1],
        "XZ_Plane": [0, -1, 0],
        "YZ_Plane": [1, 0, 0],
    }
    assert check.result["normal"] == pytest.approx(expected[plane], abs=1e-6)


@pytest.mark.asyncio
async def test_ambiguous_and_quoted_labels_are_handled(
    regression_document: tuple[XmlRpcBridge, str],
) -> None:
    """Ambiguous labels and quoted missing names return useful errors."""
    bridge, name = regression_document
    setup = await bridge.execute_python(
        f"""
import FreeCAD
doc = FreeCAD.newDocument({name!r})
a = doc.addObject('Part::Feature', 'First')
b = doc.addObject('Part::Feature', 'Second')
prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document")
previous = prefs.GetBool("DuplicateLabels", False)
try:
    prefs.SetBool("DuplicateLabels", True)
    a.Label = "Duplicate label"
    b.Label = "Duplicate label"
finally:
    prefs.SetBool("DuplicateLabels", previous)
_result_ = True
"""
    )
    assert setup.success, setup.error_traceback
    convert = _tools(bridge)["draft_shapestring_to_sketch"]
    with pytest.raises(ValueError, match="ambiguous"):
        await convert(shapestring_name="Duplicate label", doc_name=name)
    with pytest.raises(ValueError, match="ShapeString not found"):
        await convert(shapestring_name="Missing 'quoted' label", doc_name=name)
    check = await bridge.execute_python(
        f"_result_ = len(FreeCAD.getDocument({name!r}).Objects)"
    )
    assert check.success and check.result == 2


@pytest.mark.asyncio
async def test_recompute_reports_invalid_cross_document_dependency(
    tmp_path: Any,
) -> None:
    """Recompute includes invalid dependencies owned by another document."""
    suffix = uuid4().hex
    source_name = f"ExternalSource_{suffix}"
    target_name = f"ExternalTarget_{suffix}"
    bridge = XmlRpcBridge(**integration_credentials())
    await bridge.connect()
    try:
        setup = await bridge.execute_python(
            f"""
import FreeCAD
source = FreeCAD.newDocument({source_name!r})
body = source.addObject('PartDesign::Body', 'Body')
sketch = source.addObject('Sketcher::SketchObject', 'InvalidSketch')
body.addObject(sketch)
sketch.AttachmentSupport = [(body.Origin.OriginFeatures[0], '')]
sketch.MapMode = 'FlatFace'
source.recompute()
source.saveAs({str(tmp_path / "source.FCStd")!r})
target = FreeCAD.newDocument({target_name!r})
link = target.addObject('App::FeaturePython', 'ExternalLink')
link.addProperty('App::PropertyXLink', 'Source')
target.saveAs({str(tmp_path / "target.FCStd")!r})
link.Source = sketch
_result_ = list(sketch.State)
"""
        )
        assert setup.success, setup.error_traceback
        assert {"Invalid", "Error"} & set(setup.result)
        result = await _tools(bridge)["recompute_document"](doc_name=target_name)
        assert result["success"] is False
        assert any(
            obj["document"] == source_name and obj["name"] == "InvalidSketch"
            for obj in result["invalid_objects"]
        )
    finally:
        try:
            await bridge.execute_python(
                f"FreeCAD.closeDocument({target_name!r})\n"
                f"FreeCAD.closeDocument({source_name!r})\n_result_ = True"
            )
        finally:
            await bridge.disconnect()
