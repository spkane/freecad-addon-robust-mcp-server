"""Exercise reviewed document reservations against a live FreeCAD GUI."""

from uuid import uuid4

import pytest

from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.config import get_config
from tests.integration.auth_support import integration_credentials
from tests.integration.conftest import requires_gui

pytestmark = [pytest.mark.integration, pytest.mark.gui, requires_gui]


@pytest.mark.asyncio
async def test_disconnected_capture_releases_reservation_capacity() -> None:
    """More than one registry's capacity of disconnected captures can succeed."""
    name = f"McpReservation_{uuid4().hex}"
    config = get_config()
    bridge = SocketBridge(
        host=config.socket_host, port=config.socket_port, **integration_credentials()
    )
    await bridge.connect()
    try:
        setup = await bridge.execute_python(
            f"FreeCAD.newDocument({name!r})\n_result_ = True"
        )
        assert setup.success, setup.error_traceback or setup.stderr
        for _ in range(34):
            selected = await bridge.capture_review_document(name)
            assert selected and selected["name"] == name and selected["token"]
            await bridge.disconnect()
            await bridge.connect()
        final = await bridge.capture_review_document(name)
        assert final and final["token"]
        await bridge.release_review_document(final["token"])
    finally:
        try:
            await bridge.execute_python(
                f"if {name!r} in FreeCAD.listDocuments(): "
                f"FreeCAD.closeDocument({name!r})\n_result_ = True"
            )
        finally:
            await bridge.disconnect()
