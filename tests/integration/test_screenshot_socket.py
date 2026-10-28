"""Exercise screenshot captures over both authenticated FreeCAD transports."""

import base64
from uuid import uuid4

import pytest

from freecad_mcp.bridge.screenshot import build_screenshot_code
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from tests.integration.auth_support import integration_credentials
from tests.integration.conftest import requires_gui

pytestmark = [pytest.mark.integration, pytest.mark.gui, requires_gui]


@pytest.mark.parametrize("bridge_class", [SocketBridge, XmlRpcBridge])
@pytest.mark.asyncio
async def test_screenshot_renders_model_and_restores_camera(bridge_class: type) -> None:
    """A visible model changes image pixels and capture leaves the view unchanged."""
    doc_name = f"McpScreenshot_{uuid4().hex}"
    bridge = bridge_class(**integration_credentials())
    await bridge.connect()
    try:
        setup = await bridge.execute_python(
            f"""
doc = FreeCAD.newDocument({doc_name!r})
box = doc.addObject("Part::Box", "Box")
doc.recompute()
view = FreeCADGui.getDocument(doc.Name).activeView()
view.setAnimationEnabled(False)
view.viewFront()
view.fitAll()
view.setCamera(view.getCamera())
FreeCADGui.updateGui()
view.setAnimationEnabled(True)
_result_ = view.getCamera()
"""
        )
        assert setup.success, setup.error_traceback or setup.stderr
        camera = setup.result
        visible = await bridge.get_screenshot(doc_name=doc_name)
        assert visible.success, visible.error
        assert visible.data is not None
        assert base64.b64decode(visible.data, validate=True).startswith(
            b"\x89PNG\r\n\x1a\n"
        )
        state = await bridge.execute_python(
            f"""
doc = FreeCAD.getDocument({doc_name!r})
view = FreeCADGui.getDocument(doc.Name).activeView()
_result_ = {{"camera": view.getCamera(), "animation": view.isAnimationEnabled()}}
doc.getObject("Box").ViewObject.Visibility = False
FreeCADGui.updateGui()
"""
        )
        assert state.success, state.error_traceback or state.stderr
        assert state.result == {"camera": camera, "animation": True}
        failure_code = build_screenshot_code(doc_name, "Front", 320, 240)
        failure = await bridge.execute_python(
            f"""
import os
from types import SimpleNamespace
real_gui = FreeCADGui
real_view = real_gui.getDocument({doc_name!r}).activeView()
original_camera = real_view.getCamera()
class FailingView:
    path = None
    def __getattr__(self, name):
        return getattr(real_view, name)
    def saveImage(self, path, *args):
        self.path = path
        raise RuntimeError("injected screenshot failure")
failing = FailingView()
proxy = SimpleNamespace(getDocument=lambda name: SimpleNamespace(activeView=lambda: failing), updateGui=real_gui.updateGui)
try:
    exec({failure_code!r}, {{"FreeCAD": FreeCAD, "FreeCADGui": proxy}})
except RuntimeError as error:
    _result_ = {{"error": str(error), "cleaned": not os.path.exists(failing.path), "camera": real_view.getCamera(), "original": original_camera, "animation": real_view.isAnimationEnabled()}}
"""
        )
        assert failure.success, failure.error_traceback or failure.stderr
        assert failure.result["error"] == "injected screenshot failure"
        assert failure.result["cleaned"]
        assert failure.result["camera"] == failure.result["original"]
        assert failure.result["animation"] is True
        hidden = await bridge.get_screenshot(doc_name=doc_name)
        assert hidden.success, hidden.error
        assert hidden.data is not None
        pixels = await bridge.execute_python(
            f"""
import base64
from PySide import QtGui
visible = QtGui.QImage.fromData(base64.b64decode({visible.data!r}))
hidden = QtGui.QImage.fromData(base64.b64decode({hidden.data!r}))
_result_ = sum(visible.pixel(x, y) != hidden.pixel(x, y) for x in range(0, visible.width(), 8) for y in range(0, visible.height(), 8))
"""
        )
        assert pixels.success, pixels.error_traceback or pixels.stderr
        assert pixels.result > 20, "Screenshot did not show the model"
    finally:
        try:
            await bridge.execute_python(
                f"FreeCAD.closeDocument({doc_name!r})\n_result_ = True"
            )
        finally:
            await bridge.disconnect()
