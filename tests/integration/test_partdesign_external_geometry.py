"""Live FreeCAD compatibility tests for external sketch geometry counts."""

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


@pytest.mark.asyncio
async def test_live_external_geometry_count_uses_subelements() -> None:
    """Count each referenced edge when FreeCAD groups them under one object."""
    doc_name = f"McpExternalGeometry_{uuid4().hex}"
    bridge = XmlRpcBridge(**integration_credentials())
    await bridge.connect()

    try:
        setup = await bridge.execute_python(
            f"""
import FreeCAD
import Part

doc_name = {doc_name!r}
if doc_name in FreeCAD.listDocuments():
    FreeCAD.closeDocument(doc_name)
doc = FreeCAD.newDocument(doc_name)
body = doc.addObject("PartDesign::Body", "Body")
base = body.newObject("PartDesign::Feature", "BaseFeature")
base.Shape = Part.makeBox(10, 10, 10)
sketch = body.newObject("Sketcher::SketchObject", "Sketch")
doc.recompute()
_result_ = {{"document": doc.Name, "sketch": sketch.Name, "base": base.Name}}
"""
        )
        assert setup.success, setup.error_traceback or setup.stderr

        tools = _register_tools(bridge)
        for expected_count, edge_name in enumerate(
            ("Edge1", "Edge2", "Edge3"), start=1
        ):
            result = await tools["add_external_geometry"](
                sketch_name="Sketch",
                object_name="BaseFeature",
                element=edge_name,
                doc_name=doc_name,
            )
            assert result["external_geometry_count"] == expected_count

        sketch_info = await tools["get_sketch_info"](
            sketch_name="Sketch",
            doc_name=doc_name,
        )
        assert sketch_info["external_geometry_count"] == 3

        inspection = await bridge.execute_python(
            f"""
sketch = FreeCAD.getDocument({doc_name!r}).getObject("Sketch")
_result_ = {{
    "linked_object_count": len(sketch.ExternalGeometry),
    "references": [
        [linked_object.Name, list(subelements)]
        for linked_object, subelements in sketch.ExternalGeometry
    ],
}}
"""
        )
        assert inspection.success, inspection.error_traceback or inspection.stderr
        assert inspection.result == {
            "linked_object_count": 1,
            "references": [["BaseFeature", ["Edge1", "Edge2", "Edge3"]]],
        }
    finally:
        try:
            await bridge.execute_python(
                f"""
if {doc_name!r} in FreeCAD.listDocuments():
    FreeCAD.closeDocument({doc_name!r})
_result_ = True
"""
            )
        finally:
            await bridge.disconnect()
