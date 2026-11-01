"""Exercise partial bridge startup inside a real FreeCAD GUI."""

import socket
from uuid import uuid4

import pytest

from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from tests.integration.auth_support import integration_credentials
from tests.integration.conftest import requires_gui

pytestmark = [pytest.mark.integration, pytest.mark.gui, requires_gui]


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked", ["socket", "xmlrpc"])
async def test_gui_port_conflict_keeps_other_paired_listener(blocked: str) -> None:
    """A GUI bridge keeps its main-thread timer and surviving listener usable."""
    name = f"_mcp_conflict_{uuid4().hex}"
    control = XmlRpcBridge(**integration_credentials())
    await control.connect()
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        blocked_port = blocker.getsockname()[1]
        socket_port = blocked_port if blocked == "socket" else 0
        xmlrpc_port = blocked_port if blocked == "xmlrpc" else 0
        try:
            started = await control.execute_python(
                f"""
from server import FreecadMCPPlugin
plugin = FreecadMCPPlugin(host="127.0.0.1", port={socket_port}, xmlrpc_port={xmlrpc_port})
setattr(FreeCAD, {name!r}, plugin)
plugin.start()
_result_ = {{"status": plugin.get_status(), "gui_timer": plugin._timer is not None,
            "socket_port": plugin._socket_server.sockets[0].getsockname()[1] if plugin._socket_server else None,
            "xmlrpc_port": plugin._xmlrpc_server.server_address[1] if plugin._xmlrpc_server else None}}
"""
            )
            assert started.success, started.error_traceback or started.stderr
            data = started.result
            active = "xmlrpc" if blocked == "socket" else "socket"
            assert data["gui_timer"] is True
            assert data["status"]["listeners"][blocked] == "failed"
            assert data["status"]["listeners"][active] == "running"
            assert "preferences" in data["status"]["listener_errors"][blocked]
            bridge_class = SocketBridge if active == "socket" else XmlRpcBridge
            bridge = bridge_class(
                port=data[f"{active}_port"], **integration_credentials()
            )
            try:
                await bridge.connect()
                result = await bridge.execute_python("_result_ = 42")
                assert result.success and result.result == 42
            finally:
                await bridge.disconnect()
        finally:
            stopped = await control.execute_python(
                f"""
plugin = getattr(FreeCAD, {name!r}, None)
if plugin is not None:
    plugin.stop()
    delattr(FreeCAD, {name!r})
from bridge_utils import get_running_plugin
original = get_running_plugin()
if original is not None:
    original._update_status_bar()
_result_ = True
"""
            )
            await control.disconnect()
            assert stopped.success, stopped.error_traceback or stopped.stderr
