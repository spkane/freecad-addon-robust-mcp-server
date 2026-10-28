"""Verify startup timer ownership with FreeCAD's real GUI and Qt runtime."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests.integration.conftest import requires_gui

if TYPE_CHECKING:
    import xmlrpc.client

pytestmark = [pytest.mark.integration, pytest.mark.gui, requires_gui]


def test_gui_startup_cleanup_preserves_unrelated_qt_timer(
    xmlrpc_proxy: "xmlrpc.client.ServerProxy",
) -> None:
    """Cleanup stops only bridge-owned timers, leaving other workbenches intact."""
    init_path = (
        Path(__file__).resolve().parents[2]
        / "freecad"
        / "RobustMCPBridge"
        / "__init__.py"
    )
    result: dict[str, Any] = xmlrpc_proxy.execute(  # type: ignore[assignment]
        f"""
import os
import runpy
from freecad_mcp_bridge.qt_compat import load_qt_core

qtcore = load_qt_core()
previous = os.environ.get("FREECAD_MCP_TESTING")
os.environ["FREECAD_MCP_TESTING"] = "1"
try:
    state = runpy.run_path({str(init_path)!r}, run_name="mcp_cleanup_test")
finally:
    if previous is None:
        os.environ.pop("FREECAD_MCP_TESTING", None)
    else:
        os.environ["FREECAD_MCP_TESTING"] = previous
owned = qtcore.QTimer()
other = qtcore.QTimer()
owned.start(10000)
other.start(10000)
cleanup = state["_release_startup_timers"]
cleanup.__globals__["_auto_start_timer"] = owned
try:
    cleanup()
    _result_ = {{"other_active": other.isActive(), "owned_cleared": cleanup.__globals__["_auto_start_timer"] is None}}
finally:
    other.stop()
    other.deleteLater()
"""
    )
    assert result["success"], result.get("error_traceback") or result.get("stderr")
    assert result["result"] == {"other_active": True, "owned_cleared": True}
