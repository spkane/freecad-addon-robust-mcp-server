"""Temporary investigation of pocket termination semantics."""

from uuid import uuid4

import pytest

from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from tests.integration.auth_support import integration_credentials
from tests.integration.test_partdesign_symmetry import _register_tools, _setup_code


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["UpToFirst", "ThroughAll"])
async def test_symmetric_pocket_mode(mode: str) -> None:
    """Verify both sides of the cutting tool for each termination mode."""
    name = f"PocketReview_{uuid4().hex}"
    bridge = XmlRpcBridge(**integration_credentials())
    await bridge.connect()
    try:
        setup = await bridge.execute_python(_setup_code(name, True))
        assert setup.success, setup.error_traceback
        result = await _register_tools(bridge)["pocket_sketch"](
            sketch_name="Sketch", doc_name=name, symmetric=True, type=mode, length=10
        )
        inspection = await bridge.execute_python(f"""doc = FreeCAD.getDocument({name!r})
pocket = doc.getObject({result["name"]!r})
shape = pocket.AddSubShape
_result_ = {{"mode": {mode!r}, "state": list(pocket.State), "null": pocket.Shape.isNull(), "add_null": shape.isNull(), "z_min": shape.BoundBox.ZMin, "z_max": shape.BoundBox.ZMax, "removed": {result["volume_removed"]!r}, "warning": {result.get("warning")!r}}}
""")
        assert inspection.success, inspection.error_traceback
        result = inspection.result
        assert not result["null"] and not result["add_null"], result
        assert result["z_min"] < 0 < result["z_max"], result
        assert result["z_min"] == pytest.approx(-result["z_max"], abs=1e-6), result
    finally:
        await bridge.execute_python(f"FreeCAD.closeDocument({name!r})\n_result_=True")
        await bridge.disconnect()
