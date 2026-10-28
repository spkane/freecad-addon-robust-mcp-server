"""Test the production pocket tool with real FreeCAD geometry."""

from uuid import uuid4

import pytest

from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from tests.integration.auth_support import integration_credentials
from tests.integration.test_partdesign_symmetry import _register_tools

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize("reversed_cut", [False, True])
async def test_pocket_reports_real_volume_and_pending_edits(reversed_cut: bool) -> None:
    """A pending base edit is included in the baseline and a no-op is reported."""
    doc_name = f"McpPocket_{uuid4().hex}"
    bridge = XmlRpcBridge(**integration_credentials())
    await bridge.connect()
    try:
        setup = await bridge.execute_python(
            f"""
import FreeCAD
import Part

doc = FreeCAD.newDocument({doc_name!r})
body = doc.addObject("PartDesign::Body", "Body")
base = body.newObject("PartDesign::Feature", "Base")
base.Shape = Part.makeBox(20, 20, 5)
sketch = body.newObject("Sketcher::SketchObject", "Sketch")
sketch.addGeometry(Part.Circle(FreeCAD.Vector(10, 10, 0), FreeCAD.Vector(0, 0, 1), 2), False)
doc.recompute()
base.Shape = Part.makeBox(20, 20, 8)
_result_ = True
"""
        )
        assert setup.success, setup.error_traceback or setup.stderr
        pocket = _register_tools(bridge)["pocket_sketch"]
        result = await pocket(
            sketch_name="Sketch",
            length=10,
            type="ThroughAll",
            doc_name=doc_name,
            reversed=reversed_cut,
        )
        assert result["volume_before"] == pytest.approx(3200.0)
        if reversed_cut:
            assert result["volume_removed"] == pytest.approx(8 * 4 * 3.141592653589793)
            assert result["volume_after"] == pytest.approx(
                result["volume_before"] - result["volume_removed"]
            )
            assert "warning" not in result
        else:
            assert result["volume_after"] == pytest.approx(3200.0)
            assert result["volume_removed"] == pytest.approx(0.0)
            assert "warning" in result
    finally:
        try:
            await bridge.execute_python(
                f"FreeCAD.closeDocument({doc_name!r})\n_result_ = True"
            )
        finally:
            await bridge.disconnect()
