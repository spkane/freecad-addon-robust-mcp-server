"""Live FreeCAD Report view diagnostics tests."""

from uuid import uuid4

import pytest

from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from tests.integration.auth_support import integration_credentials

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize("bridge_type", [XmlRpcBridge, SocketBridge])
async def test_report_view_exposes_warning(bridge_type):
    """Both transports return a warning written to the real Report view."""
    bridge = bridge_type(**integration_credentials())
    await bridge.connect()
    try:
        if not await bridge.is_gui_available():
            pytest.skip("Report view requires the FreeCAD GUI")
        marker = f"McpReportWarning_{uuid4().hex}"
        result = await bridge.execute_python(
            f"FreeCAD.Console.PrintWarning({marker!r} + '\\n')\n"
            "FreeCADGui.updateGui()\n_result_ = True"
        )
        assert result.success, result.error_traceback or result.stderr
        assert any(marker in line for line in await bridge.get_console_output(100))
    finally:
        await bridge.disconnect()
