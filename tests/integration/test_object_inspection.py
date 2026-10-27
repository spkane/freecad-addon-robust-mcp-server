"""Exercise object inspection against real FreeCAD link properties."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from freecad_mcp.bridge.base import FreecadBridge
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from freecad_mcp.tools.objects import register_object_tools

pytestmark = pytest.mark.integration


def _register_inspect_tool(
    bridge: FreecadBridge,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Register the production inspection tool with a live bridge."""
    mcp = MagicMock()
    registered: dict[str, Callable[..., Awaitable[Any]]] = {}

    def tool() -> Callable[
        [Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]
    ]:
        def wrapper(
            func: Callable[..., Awaitable[Any]],
        ) -> Callable[..., Awaitable[Any]]:
            registered[func.__name__] = func
            return func

        return wrapper

    async def get_bridge() -> FreecadBridge:
        return bridge

    mcp.tool = tool
    register_object_tools(mcp, get_bridge)
    return registered["inspect_object"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bridge_type", [XmlRpcBridge, SocketBridge])
async def test_live_inspection_of_links_and_optional_sections(
    bridge_type: type[FreecadBridge],
) -> None:
    """Inspect a real cut and nested links through each external transport."""
    doc_name = f"McpInspect_{uuid4().hex}"
    bridge = bridge_type()
    await bridge.connect()
    try:
        setup = await bridge.execute_python(
            f"""
doc = FreeCAD.newDocument({doc_name!r})
box = doc.addObject("Part::Box", "Block")
cylinder = doc.addObject("Part::Cylinder", "Hole")
cut = doc.addObject("Part::Cut", "Cut")
cut.Base = box
cut.Tool = cylinder
cut.addProperty("App::PropertyLinkList", "Related")
cut.Related = [box, cylinder]
cut.addProperty("App::PropertyLinkSub", "EdgeReference")
cut.EdgeReference = (box, ["Edge1", "Edge2"])
empty = doc.addObject("Part::Feature", "Empty")
empty.addProperty("App::PropertyLink", "Related")
empty.Related = box
doc.recompute()
_result_ = True
"""
        )
        assert setup.success, setup.error_traceback or setup.stderr
        inspect_object = _register_inspect_tool(bridge)
        result = await inspect_object(object_name="Cut", doc_name=doc_name)
        properties = result["properties"]
        assert properties["Base"]["name"] == "Block"
        assert properties["Tool"]["name"] == "Hole"
        assert properties["Base"]["document"] == doc_name
        assert [item["name"] for item in properties["Related"]] == ["Block", "Hole"]
        assert properties["EdgeReference"][0]["name"] == "Block"
        assert properties["EdgeReference"][1] == ["Edge1", "Edge2"]
        assert result["shape_info"]["shape_type"]

        empty = await inspect_object(object_name="Empty", doc_name=doc_name)
        assert empty["properties"]["Related"]["name"] == "Block"
        assert "shape_info" not in empty

        minimal = await inspect_object(
            object_name="Cut",
            doc_name=doc_name,
            include_properties=False,
            include_shape=False,
        )
        assert minimal["name"] == "Cut"
        assert "properties" not in minimal
        assert "shape_info" not in minimal
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
