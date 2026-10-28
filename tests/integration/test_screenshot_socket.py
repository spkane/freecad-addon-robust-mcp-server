"""Exercise the socket screenshot implementation against a real FreeCAD GUI."""

import base64
from uuid import uuid4

import pytest

from freecad_mcp.bridge.socket import SocketBridge
from tests.integration.auth_support import integration_credentials
from tests.integration.conftest import requires_gui

pytestmark = [pytest.mark.integration, pytest.mark.gui, requires_gui]


@pytest.mark.asyncio
async def test_socket_screenshot_with_real_3d_view() -> None:
    """A supported 3D view produces a nonempty PNG over the socket bridge."""
    doc_name = f"McpScreenshot_{uuid4().hex}"
    bridge = SocketBridge(**integration_credentials())
    await bridge.connect()
    try:
        setup = await bridge.execute_python(
            f"""
doc = FreeCAD.newDocument({doc_name!r})
doc.addObject("Part::Box", "Box")
doc.recompute()
FreeCADGui.activeDocument().activeView().fitAll()
_result_ = True
"""
        )
        assert setup.success, setup.error_traceback or setup.stderr
        result = await bridge.get_screenshot(doc_name=doc_name)
        assert result.success, result.error
        assert result.data is not None
        image = base64.b64decode(result.data, validate=True)
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(image) > 1000
    finally:
        try:
            await bridge.execute_python(
                f"FreeCAD.closeDocument({doc_name!r})\n_result_ = True"
            )
        finally:
            await bridge.disconnect()
